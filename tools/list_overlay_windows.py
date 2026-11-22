# -*- coding: utf-8 -*-
"""列出当前可见的顶层窗口，标出 WebView2 / 浮窗 是否还挂在桌面上。"""
import ctypes
import ctypes.wintypes as wt

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WS_EX_TOPMOST = 0x00000008
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
GWL_EXSTYLE = -20
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

user32.GetWindowLongW.restype = ctypes.c_long
user32.GetWindowLongPtrW.restype = ctypes.c_longlong


def pid_of(hwnd):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def name_of(pid):
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return "?"
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            import os
            return os.path.basename(buf.value)
        return "?"
    finally:
        kernel32.CloseHandle(h)


def title_of(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def main():
    rows = []

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        pid = pid_of(hwnd)
        name = name_of(pid)
        if name.lower() not in ("msedgewebview2.exe", "python.exe", "pythonw.exe",
                                "仙友助手.exe", "worldapart.exe"):
            return True
        rect = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        flags = []
        if ex & WS_EX_TOPMOST:
            flags.append("TOPMOST")
        if ex & WS_EX_LAYERED:
            flags.append("LAYERED")
        if ex & WS_EX_NOACTIVATE:
            flags.append("NOACTIVATE")
        if ex & WS_EX_TOOLWINDOW:
            flags.append("TOOLWINDOW")
        if user32.GetWindow(hwnd, 4):  # GW_OWNER
            flags.append("OWNED")
        rows.append((name, pid, hex(hwnd), (rect.left, rect.top, rect.right - rect.left,
                                            rect.bottom - rect.top), title_of(hwnd), ",".join(flags)))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    if not rows:
        print("没有任何 WebView2 / 助手 / 游戏 的可见窗口")
        return
    for name, pid, hwnd, rect, title, flags in rows:
        print("%-18s pid=%-6s hwnd=%-10s rect=%s" % (name, pid, hwnd, rect))
        print("    标题=%r 样式=%s" % (title, flags))


if __name__ == "__main__":
    main()
