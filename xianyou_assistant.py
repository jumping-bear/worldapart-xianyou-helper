# -*- coding: utf-8 -*-
"""不问凡尘 · 仙友助手：程序入口、命令行菜单与存档监视。

具体功能拆分在 app/ 包内：
    app/modules/<key>/   每个功能一个独立模块（构建、扫描、视图）
    app/registry.py      模块注册表
    app/render.py        汇总页面数据
    app/output.py        静态页面、版本哈希与写出
"""
import json
import os
import re
import sys
import threading
import time
import webbrowser

from app.common import (  # noqa: F401  （保留旧调用方使用的模块级名字）
    APP_VERSION, BUILTIN_DIR, CFG, DEFAULT_MODULES, FROZEN, HERE, OUT_HTML, OUT_VERSION,
    _find_game_dir, _find_steam_libs, find_dir, find_save_root, load_cfg,
    original_save_index, save_cfg, save_files, source_time, state_signature, unpack)
from app import common, i18n, registry
from app.output import build_html, console_summary, disk_version, write_outputs  # noqa: F401
from app.render import render
from app.modules import bedroom

import meta_update


def _enabled_keys(cfg):
    return [spec.KEY for spec in registry.active((cfg or {}).get("modules") or {})]


def _enabled_tabs(keys):
    return [tab for tab in registry.tabs() if tab["key"] in keys]


def scan(path, meta):
    """兼容旧调用：读取一个副本并返回仙居楼互动进度。"""
    return bedroom.scan_legacy(path, meta)


def _layer_label(layer_id):
    """把修炼层 id 翻成「结丹初期 · 1 层」，内置快照缺失时退回原始编号。"""
    try:
        with open(os.path.join(BUILTIN_DIR, "realm_meta.json"), encoding="utf-8-sig") as fh:
            data = json.load(fh)
        layer = (data.get("layers") or {}).get(str(layer_id)) or {}
        phase = (data.get("phases") or {}).get(str(layer.get("phase"))) or {}
        realm = next((row for row in data.get("realms") or []
                      if row.get("id") == phase.get("realm")), {})
        if not layer:
            return "层序 %s" % layer_id
        return ("%s · %s %s 层" % (realm.get("name") or "", phase.get("name") or "",
                                  layer.get("layer") or "")).strip()
    except Exception:
        return "层序 %s" % layer_id


def _character_options(dec):
    """列出各角色最新的一份存档副本，供设置菜单选择。"""
    if not dec:
        return []
    originals = original_save_index(find_save_root())
    best = {}
    for path in save_files(dec):
        try:
            with open(path, "rb") as f:
                obj = unpack(f.read())
        except Exception:
            continue
        player = obj.get("playerModel") or {}
        name = player.get("playerName") or "未命名"
        layer = (player.get("combat") or {}).get("cultivate_layer_id") or 0
        settlements = ((player.get("random_event_settlements") or {}).get("quests") or {})
        stamp, original = source_time(path, originals)
        # 角色 key 用「角色目录 + slots」前缀：不同角色的副本文件名都是 gameworld.msgpack，
        # 只存文件名会导致固定角色失效（所有角色一起被当成固定档）。
        key = os.path.basename(path).split("_slots_", 1)[0]
        if name not in best or stamp > best[name]["stamp"]:
            best[name] = {"name": name, "layer": layer, "settle": len(settlements),
                          "stamp": stamp, "key": key,
                          "file": os.path.basename(original or path)}
    return sorted(best.values(), key=lambda item: -item["stamp"])


def settings_menu(dry_run=False):
    cfg = load_cfg()
    # 安装包目录（工坊/解压目录）里的配置可能从没定位过游戏；这时以游戏内覆盖窗口
    # 正在用的那份为基准，别把玩家现有设置显示成默认值。
    overlay_cfg = common.overlay_cfg_path(cfg)
    if overlay_cfg and not (cfg.get("game_dir") or "").strip():
        cfg = load_cfg(overlay_cfg)
    while True:
        specs = registry.MODULES
        lang = i18n.resolve(cfg, common.game_language())

        def L(zh, en):
            return en if lang == "en" else zh

        lang_name = {"auto": L("自动", "Auto"), "zh": "中文", "en": "English"}[cfg.get("ui_lang") or "auto"]
        print("\n" + L("功能设置（只读工具，不会修改游戏存档）",
                      "Settings (read-only; never modifies your save)"))
        if overlay_cfg and os.path.abspath(overlay_cfg) != os.path.abspath(common.CFG):
            print(L("配置文件：%s", "Config: %s") % common.CFG)
            print(L("游戏内覆盖窗口：%s（保存时同步写入）",
                    "In-game overlay: %s (also written on save)") % overlay_cfg)
        for index, spec in enumerate(specs, 1):
            enabled = cfg["modules"].get(spec.KEY, True)
            state = L("开启" if enabled else "关闭", "On" if enabled else "Off")
            label = getattr(spec, "LABEL_EN", None) or spec.LABEL if lang == "en" else spec.LABEL
            print("  %d. %s: %s" % (index, label, state))
        base = len(specs)
        print("  %d. %s" % (base + 1, L("重新设置解密存档目录", "Set decrypted save folder")))
        print("  %d. %s: %s" % (base + 2, L("选择存档角色", "Choose save character"),
                                cfg.get("save_name") or cfg.get("save_file")
                                or L("自动跟随最近存档", "Auto (newest save)")))
        print("  %d. %s: %s" % (base + 3, L("覆盖窗口呼出快捷键", "Overlay hotkey"),
                                cfg.get("overlay_hotkey") or common.HOTKEY_DEFAULT))
        print("  %d. %s: %s" % (base + 4, L("界面与配置文本语言", "UI and config text language"), lang_name))
        print("  %d. %s: %s" % (base + 5, L("浮窗兼容模式（关闭 GPU 加速）", "Overlay compatibility mode (no GPU)"),
                                L("开启", "On") if cfg.get("overlay_compat", True) else L("关闭", "Off")))
        if common.game_language():
            print("     " + L("游戏内语言：%s（选「自动」时跟随；手动选择会同时切换界面与配置表文本）",
                             "Game language: %s (Auto follows it; a manual choice switches both UI and config text)") % common.game_language())
        print("  0. " + L("保存并退出", "Save and exit"))
        if dry_run:
            return
        choice = input(L("请选择: ", "Select: ")).strip()
        if choice.isdigit() and 1 <= int(choice) <= base:
            key = specs[int(choice) - 1].KEY
            cfg["modules"][key] = not cfg["modules"].get(key, True)
        elif choice == str(base + 1):
            path = input(L("把 BepInEx\\decrypted 的路径粘贴到这里: ",
                           "Paste the BepInEx\\decrypted path: ")).strip().strip('"')
            if os.path.isdir(path):
                cfg["decrypted_dir"] = os.path.normpath(path)
                game = meta_update.game_dir_from_config(cfg, path)
                if game:
                    cfg["game_dir"] = game
            else:
                print(L("目录不存在，未修改。", "Folder not found; unchanged."))
        elif choice == str(base + 2):
            options = _character_options(cfg.get("decrypted_dir") or find_dir(cfg, interactive=False))
            if not options:
                print(L("还没找到可用存档。请先启动游戏，让插件导出存档副本。",
                        "No save copies yet. Start the game so the plugin can export one."))
            else:
                print("  0. " + L("自动跟随最近存档", "Auto (newest save)"))
                for index, item in enumerate(options, 1):
                    when = time.strftime("%m-%d %H:%M", time.localtime(item["stamp"])) if item["stamp"] else L("未知", "unknown")
                    print("  %d. %s · %s · %s %d · %s" % (
                        index, item["name"], _layer_label(item["layer"]),
                        L("奇遇结算", "settlements"), item["settle"], when))
                picked = input(L("选择角色: ", "Character: ")).strip()
                if picked == "0":
                    cfg["save_file"] = ""
                    cfg.pop("save_name", None)
                    print(L("已改为自动跟随最近存档。", "Now following the newest save."))
                elif picked.isdigit() and 1 <= int(picked) <= len(options):
                    chosen = options[int(picked) - 1]
                    cfg["save_file"] = chosen["key"]
                    cfg["save_name"] = chosen["name"]
                    print(L("已固定读取：%s", "Pinned to: %s") % chosen["name"])
                else:
                    print(L("输入无效，未修改。", "Invalid input; unchanged."))
        elif choice == str(base + 3):
            print(L("可选：", "Options: ") + " / ".join(common.HOTKEY_CHOICES))
            picked = input(L("输入快捷键（如 F6）: ", "Hotkey (e.g. F6): ")).strip().upper()
            if picked in common.HOTKEY_CHOICES:
                cfg["overlay_hotkey"] = picked
                print(L("已改为 %s（退出设置时保存；重启游戏后生效，覆盖窗口随游戏启动）",
                        "Set to %s (saved on exit; restart the game to apply)")
                      % picked)
            else:
                print(L("输入无效，未修改。", "Invalid input; unchanged."))
        elif choice == str(base + 4):
            picked = input("auto / zh / en: ").strip().lower()
            if picked in ("auto", "zh", "en"):
                cfg["ui_lang"] = picked
                print(L("已改为 %s（退出设置时保存；页面刷新或重启游戏后生效）。",
                        "Set to %s (saved on exit; applies after a page refresh)")
                      % picked)
            else:
                print(L("输入无效，未修改。", "Invalid input; unchanged."))
        elif choice == str(base + 5):
            cfg["overlay_compat"] = not bool(cfg.get("overlay_compat", True))
            print(L("浮窗兼容模式已%s（重启游戏后生效；若页面滚动卡顿可关闭）。",
                    "Overlay compatibility mode turned %s (applies after restarting the game; turn it off if scrolling is slow).")
                  % (L("开启", "on") if cfg["overlay_compat"] else L("关闭", "off")))
        elif choice == "0":
            if save_cfg(cfg):
                print(L("设置已保存：%s", "Saved: %s") % common.CFG)
                target = common.overlay_cfg_path(cfg)
                if target and os.path.abspath(target) != os.path.abspath(common.CFG):
                    print(L("已同步到游戏内覆盖窗口：%s（重启游戏后快捷键生效，语言会在页面刷新后自动切换）",
                            "Synced to in-game overlay: %s (hotkey applies after restarting the game)")
                          % target)
                print(L("重新打开查询工具后生效。", "Reopen the tool to apply."))
            return


def _set_console_title(text):
    """改控制台窗口标题（黑窗口容易和别的窗口混，标题里直接写明别关）。"""
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(text)
    except Exception:
        try:
            os.system("title %s" % text)
        except Exception:
            pass


# 最近一次定位到的存档副本目录，「立即同步」按钮要把信号文件写进这里。
_dec_state = {"dec": ""}


def _plugin_sync_time(dec):
    """插件上一次导出副本的时间，来自它自己写的 _status.txt。"""
    try:
        with open(os.path.join(dec or "", "_status.txt"), encoding="utf-8") as fh:
            match = re.search(r"lastSync=([\d: -]+)", fh.read())
        return match.group(1).strip() if match else ""
    except OSError:
        return ""


def request_sync():
    """浮窗按钮调用：让插件立刻导出一次存档副本，并唤醒本进程的轮询。"""
    dec = _dec_state.get("dec") or ""
    requested = False
    if dec and os.path.isdir(dec):
        try:
            with open(os.path.join(dec, common.SYNC_FLAG), "w", encoding="utf-8") as fh:
                fh.write(time.strftime("%Y-%m-%d %H:%M:%S"))
            requested = True
        except OSError:
            requested = False
    common.SYNC_EVENT.set()
    return {"requested": requested, "plugin": _plugin_sync_time(dec)}


# 网页版「立即同步」：本机回环端口，页面用 <script> 请求 /sync 通知插件马上导出。
_sync_http = {"port": 0}


def _start_sync_server():
    """启动只监听 127.0.0.1 的小服务；返回端口，失败返回 0。"""
    if _sync_http["port"]:
        return _sync_http["port"]
    try:
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    except Exception:
        return 0
    script = b"window.__syncAck=(window.__syncAck||0)+1;"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if not self.path.startswith("/sync"):
                self.send_response(404)
                self.end_headers()
                return
            try:
                request_sync()
            except Exception:
                pass
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(script)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(script)

        def log_message(self, fmt, *args):
            return

    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    except Exception as exc:
        print("网页版「立即同步」不可用：%s" % exc)
        return 0
    _sync_http["port"] = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return _sync_http["port"]


def watch(open_browser=True, once=False, interactive=True):
    """监视存档并持续生成页面；overlay 模式下由后台线程调用。"""
    cfg = load_cfg()
    enabled = _enabled_keys(cfg)
    dec = find_dir(cfg, interactive=interactive and bool(enabled))
    opened = False
    last_signature = None
    fast_until = 0.0
    sync_url = ""
    if not common.OVERLAY_MODE and not once:
        port = _start_sync_server()
        if port:
            sync_url = "http://127.0.0.1:%d/sync" % port
    print("已生成：%s" % common.OUT_HTML)
    while True:
        try:
            cfg = load_cfg()
            enabled = _enabled_keys(cfg)
            if enabled and (not dec or not os.path.isdir(dec)):
                dec = find_dir(cfg, interactive=interactive and last_signature is None)
            _dec_state["dec"] = dec or ""
            if common.SYNC_EVENT.is_set():
                # 玩家点了「立即同步」：插件那边马上导出，这边也切到 1 秒轮询，
                # 十几秒内没跟上就退回常态间隔。
                common.SYNC_EVENT.clear()
                fast_until = time.time() + 8
            signature = state_signature(dec, cfg)
            if signature != last_signature or not os.path.exists(common.OUT_HTML):
                payload = render(dec, cfg) if dec or not enabled else {
                    "enabled": enabled,
                    "tabs": _enabled_tabs(enabled),
                    "modules": {}, "warnings": common.missing_hints(cfg),
                }
                payload["sync_url"] = sync_url
                lang = i18n.resolve(cfg, common.game_language())
                payload["lang"] = lang
                payload["i18n"] = i18n.terms(lang)
                version, changed = write_outputs(payload)
                if changed or last_signature is None:
                    console_summary(payload)
                if changed and last_signature is not None:
                    print("[%s] 数据已更新" % time.strftime("%H:%M:%S"))
                last_signature = state_signature(dec, cfg)
            if open_browser and not opened:
                try:
                    webbrowser.open("file:///" + common.OUT_HTML.replace("\\", "/"))
                except Exception:
                    pass
                opened = True
            if once:
                return
            poll = 1 if time.time() < fast_until else 2.5
            common.SYNC_EVENT.wait(poll)
        except KeyboardInterrupt:
            return
        except Exception as e:
            print("监视结束：%s" % e)
            return


def main():
    if FROZEN:
        try:
            os.system("chcp 65001 >nul")
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        _set_console_title("仙友助手 - 功能设置" if "--settings" in sys.argv
                           else "仙友助手 - 使用过程中请勿关闭这个窗口")
    if "--settings" in sys.argv:
        settings_menu(dry_run="--dry-run" in sys.argv)
        return
    if "--out-dir" in sys.argv:
        common.set_output_dir(sys.argv[sys.argv.index("--out-dir") + 1])
    once = "--once" in sys.argv
    if "--overlay" in sys.argv:
        import threading

        from app.overlay import run as run_overlay, watch_parent
        common.OVERLAY_MODE = True
        if "--parent-pid" in sys.argv:
            try:
                parent = int(sys.argv[sys.argv.index("--parent-pid") + 1])
                threading.Thread(target=watch_parent, args=(parent,), daemon=True).start()
            except ValueError:
                pass
        threading.Thread(target=watch, kwargs={"open_browser": False, "interactive": False},
                         daemon=True).start()
        run_overlay(common.OUT_HTML, start_hidden="--silent" in sys.argv,
                    hotkey=load_cfg().get("overlay_hotkey") or common.HOTKEY_DEFAULT,
                    compat=bool(load_cfg().get("overlay_compat", True)),
                    on_sync=request_sync)
        return
    watch(open_browser="--no-browser" not in sys.argv, once=once)


if __name__ == "__main__":
    main()
