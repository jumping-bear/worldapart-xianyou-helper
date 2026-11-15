# -*- coding: utf-8 -*-
"""不问凡尘 · 仙友助手：程序入口、命令行菜单与存档监视。

具体功能拆分在 app/ 包内：
    app/common.py        常量、配置、存档定位
    app/scanners/*.py    每个功能一个扫描模块
    app/registry.py      模块注册表
    app/render.py        汇总页面数据
    app/output.py        静态页面、版本哈希与写出
"""
import os
import sys
import time
import webbrowser

from app.common import (  # noqa: F401  （保留旧调用方使用的模块级名字）
    APP_VERSION, BUILTIN_DIR, CFG, DEFAULT_MODULES, FROZEN, HERE, OUT_HTML, OUT_VERSION,
    _find_game_dir, _find_steam_libs, find_dir, find_save_root, load_cfg,
    original_save_index, save_cfg, save_files, source_time, state_signature, unpack)
from app.output import build_html, console_summary, disk_version, write_outputs  # noqa: F401
from app.render import render
from app.scanners import bedroom

import meta_update


def scan(path, meta):
    """兼容旧调用：读取一个副本并返回仙居楼互动进度。"""
    return bedroom.scan_legacy(path, meta)


def settings_menu():
    cfg = load_cfg()
    while True:
        print("\n功能设置（只读工具，不会修改游戏存档）")
        print("  1. 仙居楼互动（十八摸成就）：%s" % ("开启" if cfg["modules"]["bedroom"] else "关闭"))
        print("  2. NPC天赋：%s" % ("开启" if cfg["modules"]["talent"] else "关闭"))
        print("  3. NPC物品：%s" % ("开启" if cfg["modules"]["items"] else "关闭"))
        print("  4. 炼丹：%s" % ("开启" if cfg["modules"]["pill"] else "关闭"))
        print("  5. 炼器：%s" % ("开启" if cfg["modules"]["forge"] else "关闭"))
        print("  6. 奇遇：%s" % ("开启" if cfg["modules"]["event"] else "关闭"))
        print("  7. 重新设置解密存档目录")
        print("  0. 保存并退出")
        choice = input("请选择: ").strip()
        if choice in ("1", "2", "3", "4", "5", "6"):
            name = {"1": "bedroom", "2": "talent", "3": "items", "4": "pill",
                    "5": "forge", "6": "event"}[choice]
            cfg["modules"][name] = not cfg["modules"][name]
        elif choice == "7":
            path = input("把 BepInEx\\decrypted 的路径粘贴到这里: ").strip().strip('"')
            if os.path.isdir(path):
                cfg["decrypted_dir"] = os.path.normpath(path)
                game = meta_update.game_dir_from_config(cfg, path)
                if game:
                    cfg["game_dir"] = game
            else:
                print("目录不存在，未修改。")
        elif choice == "0":
            if save_cfg(cfg):
                print("设置已保存。重新打开查询工具后生效。")
            return


def main():
    if FROZEN:
        try:
            os.system("chcp 65001 >nul")
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if "--settings" in sys.argv:
        settings_menu()
        return
    cfg = load_cfg()
    dec = find_dir(cfg, interactive=any(cfg["modules"].values()))
    opened = False
    last_signature = None
    print("已生成：%s" % OUT_HTML)
    while True:
        try:
            cfg = load_cfg()
            if any(cfg["modules"].values()) and (not dec or not os.path.isdir(dec)):
                dec = find_dir(cfg, interactive=last_signature is None)
            signature = state_signature(dec, cfg)
            if signature != last_signature or not os.path.exists(OUT_HTML):
                payload = render(dec, cfg) if dec or not any(cfg["modules"].values()) else {
                    "enabled": [n for n in ("bedroom", "talent", "items", "pill", "forge", "event")
                                if cfg["modules"][n]],
                    "modules": {}, "warnings": ["未设置解密存档目录，请重新安装或运行功能设置。"],
                }
                version, changed = write_outputs(payload)
                if changed or last_signature is None:
                    console_summary(payload)
                if changed and last_signature is not None:
                    print("[%s] 数据已更新" % time.strftime("%H:%M:%S"))
                last_signature = state_signature(dec, cfg)
            if not opened:
                try:
                    webbrowser.open("file:///" + OUT_HTML.replace("\\", "/"))
                except Exception:
                    pass
                opened = True
            if "--once" in sys.argv:
                return
            time.sleep(3)
        except KeyboardInterrupt:
            return
        except Exception as e:
            print("监视结束：%s" % e)
            return


if __name__ == "__main__":
    main()
