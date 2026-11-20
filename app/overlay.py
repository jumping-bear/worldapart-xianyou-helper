# -*- coding: utf-8 -*-
"""覆盖模式：把查询页面变成游戏中可随时呼出的悬浮面板。

设计要点：
* 页面复用 build_html 的产物，不维护第二套前端；
* pywebview（WebView2）承载页面，窗口无边框、置顶；
* F3 走系统级热键 RegisterHotKey，游戏在前台时同样生效；
* 显隐、定位全部直接操作 Win32 窗口句柄，避免跨线程调用 UI 框架。
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import tempfile
import threading
import time

import webview

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_HOTKEY = 0x0312
WM_NCLBUTTONDOWN = 0x00A1
HTCAPTION = 2
# 浮窗三档尺寸（占屏幕比例）：小 / 中 / 大
SIZE_LEVELS = (0.60, 0.75, 0.82)
MOD_NOREPEAT = 0x4000
VK_F3 = 0x72
HOTKEYS = {"F%d" % i: 0x6F + i for i in range(1, 13)}  # F1=0x70 … F12=0x7B
GW_OWNER = 4
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
SW_SHOW = 5
HWND_TOPMOST = ctypes.c_void_p(-1)  # 64 位下必须按指针传递，传 -1 会被截断导致移动静默失败
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000

user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wt.UINT]
user32.SetWindowPos.restype = wt.BOOL
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetWindowRect.restype = wt.BOOL
user32.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.SendMessageW.restype = wt.LPARAM

WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
GAME_EXE = "worldapart.exe"
WINDOW_TITLE = "仙友助手"


def _system_scale():
    """系统显示缩放比（1.0 / 1.25 / 1.5 / 3.0 …），用于补偿 WebView2 的 DPR 偏差。"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Control Panel\Desktop\WindowMetrics") as key:
            dpi = winreg.QueryValueEx(key, "AppliedDPI")[0] or 96
        return max(1.0, dpi / 96.0)
    except Exception:
        return 1.0


def _dpi_aware():
    """让进程按物理像素工作，避免 150% 缩放下窗口尺寸算错。"""
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
        return
    except Exception:
        pass
    try:
        ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


def _pid_of(hwnd):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


_name_cache = {}


def _process_name(pid):
    if pid in _name_cache:
        return _name_cache[pid]
    name = ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if handle:
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wt.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                name = os.path.basename(buf.value).lower()
        finally:
            kernel32.CloseHandle(handle)
    _name_cache[pid] = name
    return name


def _visible_windows():
    found = []

    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, GW_OWNER):
            return True
        rect = wt.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return True
        if rect.right - rect.left <= 0 or rect.bottom - rect.top <= 0:
            return True
        found.append((hwnd, (rect.right - rect.left) * (rect.bottom - rect.top)))
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return found


def _client_rect(hwnd):
    """窗口客户区在屏幕上的物理坐标 (x, y, w, h)。"""
    rect = wt.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    point = wt.POINT(0, 0)
    if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
        return None
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return None
    return point.x, point.y, width, height


def find_game_window():
    """游戏客户区；游戏没开或最小化时返回 None。"""
    best = None
    for hwnd, area in _visible_windows():
        if _process_name(_pid_of(hwnd)) == GAME_EXE:
            if user32.IsIconic(hwnd):
                continue
            if best is None or area > best[1]:
                best = (hwnd, area)
    if not best:
        return None, None
    return best[0], _client_rect(best[0])


LOADING_HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
html,body{height:100%;margin:0;background:#0e1014;color:#e8eaed;
font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif}
.box{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px}
.spin{width:34px;height:34px;border:3px solid #2a3341;border-top-color:#3ddc84;border-radius:50%;
animation:r 1s linear infinite}@keyframes r{to{transform:rotate(360deg)}}
.t{font-size:16px}.s{color:#8b93a1;font-size:12px;line-height:1.8;text-align:center}
</style></head><body><div class="box"><div class="spin"></div>
<div class="t">正在读取存档…</div>
<div class="s">首次启动需要生成适配文件，约 1~3 分钟，请稍候<br>按 F3 可先收起</div></div></body></html>"""


def _file_url(path):
    return "file:///" + os.path.abspath(path).replace("\\", "/")


def _write_loading_page():
    path = os.path.join(tempfile.gettempdir(), "xianyou_assistant_loading.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(LOADING_HTML)
    return _file_url(path)


def _await_page(window, html_path, controller=None, show_after=False):
    """页面首次生成可能要好几分钟，生成后把占位页换成真实页面。"""
    url = _file_url(html_path)
    while True:
        try:
            if os.path.exists(html_path) and os.path.getsize(html_path) > 0:
                time.sleep(0.3)
                window.load_url(url)
                print("[overlay] 页面已就绪，切换完成", flush=True)
                if show_after and controller:
                    # 切换导航会把窗口状态重置为隐藏，这里恢复一次。
                    time.sleep(0.8)
                    controller.show()
                return
        except Exception:
            pass
        time.sleep(1)


def _set_noactivate(hwnd, enabled=True):
    """让浮窗不抢焦点：游戏保持前台，声音和画面不会因失焦中断。"""
    try:
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = (style | WS_EX_NOACTIVATE) if enabled else (style & ~WS_EX_NOACTIVATE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    except Exception:
        pass


def _logical_screen():
    """屏幕逻辑尺寸：pywebview 的窗口坐标按逻辑像素处理，这里换算回去。"""
    try:
        dpi = user32.GetDpiForSystem()
    except Exception:
        dpi = 96
    scale = (dpi or 96) / 96.0
    return user32.GetSystemMetrics(0) / scale, user32.GetSystemMetrics(1) / scale


def _decorate(hwnd):
    """Win11 下给浮窗加圆角与描边；系统不支持时静默跳过。"""
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        dwmapi.DwmSetWindowAttribute(wt.HWND(hwnd), 33, ctypes.byref(pref), 4)
        border = ctypes.c_int(0x003A2A20)  # COLORREF(0x00BBGGRR) ≈ #202A3A
        dwmapi.DwmSetWindowAttribute(wt.HWND(hwnd), 34, ctypes.byref(border), 4)
    except Exception:
        pass


def _force_foreground(hwnd):
    """强行把窗口提到前台：跨进程 SetForegroundWindow 会被系统拦截，需要线程输入附加。"""
    try:
        if user32.GetForegroundWindow() == hwnd:
            return
        target = user32.GetWindowThreadProcessId(hwnd, None)
        current = kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(target, current, True)
        user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(target, current, False)
    except Exception:
        pass


def _make_api(window_ref, controller):
    """暴露给页面的 JS 接口：window.pywebview.api.hide() / quit()。

    pywebview 会递归遍历 js_api 对象的属性并序列化，所以 controller 和 window
    只能通过闭包访问，不能作为属性挂上去（否则会遍历到 WinForms 控件树报错）。
    """

    class Api:
        def hide(self):
            controller.hide()
            return True

        def activate(self):
            controller.activate()
            return True

        def drag_start(self):
            controller.drag_start()
            return True

        def drag_move(self):
            controller.drag_move()
            return True

        def drag_end(self):
            controller.drag_end()
            return True

        def set_size(self, level):
            return controller.set_size(level)

        def quit(self):
            window = window_ref()
            if window:
                window.destroy()
            return True

    return Api()


def watch_parent(pid):
    """由游戏插件拉起时，游戏退出（含崩溃）后自动结束本进程，避免残留。"""
    kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    kernel32.OpenProcess.restype = wt.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
    kernel32.WaitForSingleObject.restype = wt.DWORD
    kernel32.CloseHandle.argtypes = [wt.HANDLE]
    synchronize = 0x00100000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | synchronize, False, pid)
    if not handle:
        os._exit(0)
    try:
        while True:
            if kernel32.WaitForSingleObject(handle, 5000) == 0:  # WAIT_OBJECT_0：父进程已退出
                os._exit(0)
    finally:
        kernel32.CloseHandle(handle)


class Controller:
    def __init__(self, hwnd_getter, visible=True, size_level=2, on_geometry=None):
        self._get_hwnd = hwnd_getter
        self._visible = visible
        self.size_level = max(0, min(len(SIZE_LEVELS) - 1, int(size_level)))
        self._on_geometry = on_geometry
        self._drag_offset = None

    def hwnd(self):
        return self._get_hwnd()

    def show(self):
        hwnd = self.hwnd()
        if not hwnd:
            return
        started = time.perf_counter()
        # 只保证"显示时不激活"，不禁止窗口被激活：否则鼠标点击会被系统吞掉，页面无法操作。
        user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        self._visible = True
        print("[overlay] 呼出耗时 %.1f ms" % ((time.perf_counter() - started) * 1000), flush=True)

    def activate(self):
        """页面里需要打字（搜索框等）时才把浮窗激活，用完收起即可恢复游戏焦点。"""
        hwnd = self.hwnd()
        if not hwnd:
            return
        _set_noactivate(hwnd, False)
        _force_foreground(hwnd)

    def hide(self):
        hwnd = self.hwnd()
        if not hwnd:
            return
        started = time.perf_counter()
        # 离屏/移边缘都会让 WebView2 丢合成层，恢复时黑屏或半黑，只能老实隐藏。
        was_foreground = user32.GetForegroundWindow() == hwnd
        user32.ShowWindow(hwnd, SW_HIDE)
        self._visible = False
        # 只有浮窗当前真的持有焦点（点过页面）时才把焦点还给游戏。
        if was_foreground:
            game, _ = find_game_window()
            if game:
                _force_foreground(game)
        print("[overlay] 收起耗时 %.1f ms" % ((time.perf_counter() - started) * 1000), flush=True)

    def drag_start(self):
        """记录按下时鼠标在窗口内的偏移，后续用相对位移移动窗口。"""
        hwnd = self.hwnd()
        if not hwnd:
            return
        point = wt.POINT()
        rect = wt.RECT()
        if not user32.GetCursorPos(ctypes.byref(point)):
            return
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return
        self._drag_offset = (point.x - rect.left, point.y - rect.top)

    def drag_move(self):
        hwnd = self.hwnd()
        if not hwnd or not self._drag_offset:
            return
        point = wt.POINT()
        if not user32.GetCursorPos(ctypes.byref(point)):
            return
        dx, dy = self._drag_offset
        user32.SetWindowPos(hwnd, HWND_TOPMOST, point.x - dx, point.y - dy, 0, 0,
                            SWP_NOSIZE | SWP_NOACTIVATE)

    def drag_end(self):
        self._drag_offset = None
        hwnd = self.hwnd()
        if not hwnd:
            return
        rect = wt.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            self._notify(rect.left, rect.top)

    def set_size(self, level):
        """按档位设置窗口大小并居中，记住档位与位置。"""
        hwnd = self.hwnd()
        if not hwnd:
            return False
        self.size_level = max(0, min(len(SIZE_LEVELS) - 1, int(level)))
        ratio = SIZE_LEVELS[self.size_level]
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        width, height = int(screen_w * ratio), int(screen_h * ratio)
        x, y = (screen_w - width) // 2, (screen_h - height) // 2
        user32.SetWindowPos(hwnd, HWND_TOPMOST, x, y, width, height, SWP_NOACTIVATE)
        self._notify(x, y)
        return True

    def _notify(self, x, y):
        if self._on_geometry:
            try:
                self._on_geometry(int(x), int(y), self.size_level)
            except Exception:
                pass

    def toggle(self):
        if self._visible:
            self.hide()
        else:
            self.show()




class Hotkey(threading.Thread):
    """独立线程注册系统热键，避免和 WebView 的消息循环抢线程。"""

    def __init__(self, callback, vk=VK_F3, name="F3"):
        super().__init__(daemon=True)
        self._callback = callback
        self._vk = vk
        self._name = name
        self.registered = False

    def run(self):
        self.registered = bool(user32.RegisterHotKey(None, 1, MOD_NOREPEAT, self._vk))
        if not self.registered:
            print("[overlay] %s 热键注册失败，可能已被其他程序或游戏占用" % self._name)
            return
        print("[overlay] %s 热键已注册" % self._name)
        msg = wt.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    try:
                        self._callback()
                    except Exception:
                        pass
        finally:
            user32.UnregisterHotKey(None, 1)


INJECT_JS = r"""
(function(){
  if (document.getElementById('xy-bar')) return;
  var css = document.createElement('style');
  css.textContent = [
    'body{padding-top:60px!important;box-shadow:inset 0 0 0 1px #2a3341}',
    '.wrap{max-width:1560px}',
    '#xy-bar{position:fixed;left:0;right:0;top:0;height:46px;display:flex;align-items:center;gap:10px;',
    'padding:0 16px;background:rgba(14,17,22,.97);border-bottom:1px solid #29303c;z-index:99999;',
    'font:12px/1.4 "Microsoft YaHei",system-ui,sans-serif;color:#8b93a1}',
    '#xy-bar .t{color:#c9f5dd;font-weight:600;font-size:13px}',
    '#xy-bar .h{margin-left:auto;display:flex;gap:8px}',
    '#xy-bar button{background:#1b222c;border:1px solid #35404f;color:#c6cfda;border-radius:7px;',
    'padding:6px 12px;font-size:12px;cursor:pointer;font-family:inherit}',
    '#xy-bar button:hover{background:#25303d}',
    '#xy-bar button.quit:hover{border-color:#6b3a44;color:#e88b82}',
    '#xy-bar .zoom{display:flex;align-items:center;gap:5px;margin-left:6px}',
    '#xy-bar .zoom button{padding:4px 9px;min-width:32px}',
    '#xy-bar .zoom span{min-width:44px;text-align:center;color:#c6cfda;cursor:pointer}',
    '#xy-bar .sizes{display:flex;gap:4px;margin-left:8px}',
    '#xy-bar .sizes button{padding:4px 8px;min-width:30px}',
    '#xy-bar .sizes button.on{background:#1f3b30;border-color:#3f6d57;color:#bff0d5}'
  ].join('');
  document.head.appendChild(css);
  var bar = document.createElement('div');
  bar.id = 'xy-bar';
  bar.innerHTML = '<span class="t">仙友助手 · 覆盖模式</span>' +
    '<span>__HOTKEY__ 收起 / 呼出 · ESC 隐藏</span>' +
    '<span class="zoom"><button id="xy-zoom-out" title="缩小">A−</button>' +
    '<span id="xy-zoom-val">100%</span>' +
    '<button id="xy-zoom-in" title="放大">A+</button></span>' +
    '<span class="sizes"><button data-size="0" title="小窗">小</button>' +
    '<button data-size="1" title="中窗">中</button>' +
    '<button data-size="2" title="大窗">大</button></span>' +
    '<span class="h"><button id="xy-hide">收起</button>' +
    '<button class="quit" id="xy-quit">退出工具</button></span>';
  document.body.appendChild(bar);
  document.getElementById('xy-hide').onclick = function(){ window.pywebview.api.hide(); };
  document.getElementById('xy-quit').onclick = function(){ window.pywebview.api.quit(); };
  // 缩放：50%~250%，步进 10%，点百分比回到 100%，比例记在本机。
  // 部分环境下 WebView2 的 devicePixelRatio 为 1，视口会按物理像素计算；
  // 用系统缩放补偿，保证布局宽度与设计基准一致。
  var baseZoom = (window.devicePixelRatio === 1) ? __DPI_SCALE__ : 1;
  var zoom = parseInt(localStorage.getItem('xy-zoom') || '100', 10) || 100;
  function applyZoom(value){
    zoom = Math.max(50, Math.min(250, value));
    document.documentElement.style.zoom = (zoom / 100) * baseZoom;
    var label = document.getElementById('xy-zoom-val');
    if (label) label.textContent = zoom + '%';
    try { localStorage.setItem('xy-zoom', String(zoom)); } catch (err) {}
  }
  document.getElementById('xy-zoom-out').onclick = function(){ applyZoom(zoom - 10); };
  document.getElementById('xy-zoom-in').onclick = function(){ applyZoom(zoom + 10); };
  document.getElementById('xy-zoom-val').onclick = function(){ applyZoom(100); };
  applyZoom(zoom);
  // 窗口三档尺寸 + 顶栏拖动
  var sizeLevel = __SIZE_LEVEL__;
  function markSize(){
    document.querySelectorAll('#xy-bar .sizes button').forEach(function(btn){
      btn.classList.toggle('on', Number(btn.dataset.size) === sizeLevel);
    });
  }
  document.querySelectorAll('#xy-bar .sizes button').forEach(function(btn){
    btn.onclick = function(){
      sizeLevel = Number(btn.dataset.size);
      markSize();
      try { window.pywebview.api.set_size(sizeLevel); } catch (err) {}
    };
  });
  markSize();
  var dragOn = false, dragWait = false;
  bar.addEventListener('mousedown', function(e){
    if (e.button !== 0) return;
    var tag = (e.target.tagName || '').toUpperCase();
    if (tag === 'BUTTON' || tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
    dragOn = true;
    try { window.pywebview.api.drag_start(); } catch (err) {}
  });
  document.addEventListener('mousemove', function(){
    if (!dragOn || dragWait) return;
    dragWait = true;
    setTimeout(function(){
      dragWait = false;
      if (dragOn) { try { window.pywebview.api.drag_move(); } catch (err) {} }
    }, 30);
  });
  document.addEventListener('mouseup', function(){
    if (!dragOn) return;
    dragOn = false;
    try { window.pywebview.api.drag_end(); } catch (err) {}
  });
  // 记住滚动位置（按页签区分），存档刷新后接着看，不会跳回顶部或停到错乱处。
  try { if ('scrollRestoration' in history) history.scrollRestoration = 'manual'; } catch (err) {}
  function scrollBox(){
    var box = document.querySelector('.wrapper');
    if (box && box.scrollHeight > box.clientHeight + 10) return box;
    return document.scrollingElement || document.documentElement;
  }
  function activeTab(){
    try { return localStorage.getItem('worldapart.active.tab.v2') || ''; } catch (err) { return ''; }
  }
  var scrollTimer = null;
  document.addEventListener('scroll', function(){
    if (scrollTimer) return;
    scrollTimer = setTimeout(function(){
      scrollTimer = null;
      try {
        localStorage.setItem('xy-scroll', JSON.stringify({
          tab: activeTab(), top: scrollBox().scrollTop || 0
        }));
      } catch (err) {}
    }, 300);
  }, true);
  function restoreScroll(){
    var data = {}, box = scrollBox();
    try { data = JSON.parse(localStorage.getItem('xy-scroll') || '{}'); } catch (err) {}
    if (data.tab !== activeTab() || !data.top) return;
    box.scrollTop = Math.min(data.top, Math.max(0, box.scrollHeight - box.clientHeight));
  }
  window.addEventListener('load', function(){
    setTimeout(restoreScroll, 80);
    setTimeout(restoreScroll, 500);
  });
  document.addEventListener('wheel', function(e){
    if (!e.ctrlKey) return;
    e.preventDefault();
    applyZoom(zoom + (e.deltaY < 0 ? 10 : -10));
  }, { passive: false });
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape') window.pywebview.api.hide();
  });
  // 浮窗默认不抢焦点（避免游戏失焦静音）；点到输入框时才激活窗口，保证能打字。
  document.addEventListener('mousedown', function(e){
    var t = e.target;
    if (!t || !t.tagName) return;
    var tag = t.tagName.toUpperCase();
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') {
      try { window.pywebview.api.activate(); } catch (err) {}
      setTimeout(function(){ try { t.focus(); } catch (err) {} }, 150);
    }
  }, true);
})();
"""


def _state_path(html_path):
    return os.path.join(os.path.dirname(os.path.abspath(html_path)), "config.json")


def _read_overlay_state(html_path):
    """读取窗口档位与记忆位置；文件不存在或字段异常时回落到默认。"""
    try:
        with open(_state_path(html_path), encoding="utf-8") as file:
            data = json.load(file)
        level = int(data.get("overlay_size", 2))
        level = max(0, min(len(SIZE_LEVELS) - 1, level))
        pos = data.get("overlay_pos")
        if not (isinstance(pos, list) and len(pos) == 2):
            pos = None
        return level, pos
    except Exception:
        return len(SIZE_LEVELS) - 1, None


def _save_overlay_state(html_path, x, y, level):
    path = _state_path(html_path)
    try:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
    except Exception:
        data = {}
    data["overlay_pos"] = [int(x), int(y)]
    data["overlay_size"] = int(level)
    try:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
    except Exception:
        pass


def run(html_path, title=WINDOW_TITLE, start_hidden=False, hotkey="F3"):
    """阻塞运行覆盖窗口，直到用户点击「退出工具」。"""
    _dpi_aware()
    hotkey = str(hotkey or "F3").upper()
    vk = HOTKEYS.get(hotkey)
    if vk is None:
        hotkey, vk = "F3", VK_F3
    size_level, saved_pos = _read_overlay_state(html_path)
    inject_js = (INJECT_JS.replace("__HOTKEY__", hotkey)
                 .replace("__DPI_SCALE__", "%g" % _system_scale())
                 .replace("__SIZE_LEVEL__", str(size_level)))
    ready = os.path.exists(html_path) and os.path.getsize(html_path) > 0
    url = _file_url(html_path) if ready else _write_loading_page()

    holder = {}
    window_holder = {}
    controller = Controller(
        lambda: holder.get("hwnd") or 0, visible=not start_hidden,
        size_level=size_level,
        on_geometry=lambda x, y, level: _save_overlay_state(html_path, x, y, level),
    )
    api = _make_api(lambda: window_holder.get("window"), controller)
    window = webview.create_window(
        title, url, js_api=api,
        width=1000, height=700, hidden=start_hidden,
        frameless=True, on_top=True, easy_drag=False, resizable=False,
        background_color="#0e1014",
    )
    window_holder["window"] = window

    def locate(_window=None):
        # 无边框窗口仍然保留标题，优先按标题找，找不到再退回本进程可见窗口。
        hwnd = user32.FindWindowW(None, title)
        if not hwnd:
            for candidate, _area in _visible_windows():
                if _pid_of(candidate) == os.getpid():
                    hwnd = candidate
                    break
        if hwnd:
            holder["hwnd"] = hwnd
        return hwnd

    def inject(_window=None):
        try:
            window.evaluate_js(inject_js)
        except Exception:
            pass

    def on_closed(_window=None):
        print("[overlay] 窗口已关闭")

    if not ready:
        threading.Thread(target=_await_page,
                         args=(window, html_path, controller, not start_hidden),
                         daemon=True).start()

    def on_shown(_window=None):
        # pywebview 的 start(func) 在窗口创建之前就执行，句柄只能在 shown 之后取。
        def prepare():
            hwnd = 0
            for _ in range(30):
                hwnd = locate()
                if hwnd:
                    break
                time.sleep(0.1)
            # GetSystemMetrics 与 SetWindowPos 在同一个 DPI 坐标系下，直接设置物理/虚拟像素，
            # 不经过 pywebview 的 resize/move（它会再乘一次系统缩放，导致视口错位）。
            ratio = SIZE_LEVELS[controller.size_level]
            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
            width, height = int(screen_w * ratio), int(screen_h * ratio)
            x, y = (screen_w - width) // 2, (screen_h - height) // 2
            if saved_pos:
                px, py = saved_pos
                # 记忆位置来自别的分辨率时，越界就回到居中，避免窗口跑到屏幕外。
                if 0 <= px <= screen_w - 100 and 0 <= py <= screen_h - 100:
                    x, y = int(px), int(py)
            if hwnd:
                user32.SetWindowPos(hwnd, HWND_TOPMOST, x, y, width, height, SWP_NOACTIVATE)
            print("[overlay] 窗口句柄 %s，浮窗 %dx%d" % (hex(hwnd) if hwnd else "未找到",
                                                        width, height), flush=True)

            _decorate(hwnd)
            if start_hidden:
                # 随游戏自动启动时先收起来，玩家按快捷键再呼出。
                controller.hide()
            else:
                controller.show()
                # 打包版在部分机器上首次 Show 会被窗口初始化流程覆盖成隐藏，这里兜底一次。
                time.sleep(0.5)
                if hwnd and not user32.IsWindowVisible(hwnd):
                    print("[overlay] 首次显示被隐藏，自动恢复", flush=True)
                    controller.show()

        threading.Thread(target=prepare, daemon=True).start()
        Hotkey(controller.toggle, vk=vk, name=hotkey).start()

    window.events.loaded += inject
    window.events.shown += on_shown
    window.events.closed += on_closed

    # 窗口隐藏时不让 Chromium 降级渲染/释放合成资源，减少再次呼出时的重绘开销。
    os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
                          "--disable-backgrounding-occluded-windows --disable-renderer-backgrounding")
    webview.start(gui="edgechromium")
    print("[overlay] 主循环结束")
