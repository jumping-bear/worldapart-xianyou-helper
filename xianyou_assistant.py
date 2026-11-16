# -*- coding: utf-8 -*-
"""不问凡尘 · 仙友助手：程序入口、命令行菜单与存档监视。

具体功能拆分在 app/ 包内：
    app/modules/<key>/   每个功能一个独立模块（构建、扫描、视图）
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
from app import registry
from app.modules import bedroom

import meta_update


def _enabled_keys(cfg):
    return [spec.KEY for spec in registry.active((cfg or {}).get("modules") or {})]


def _enabled_tabs(keys):
    return [tab for tab in registry.tabs() if tab["key"] in keys]


def scan(path, meta):
    """兼容旧调用：读取一个副本并返回仙居楼互动进度。"""
    return bedroom.scan_legacy(path, meta)


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
        if name not in best or stamp > best[name]["stamp"]:
            best[name] = {"name": name, "layer": layer, "settle": len(settlements),
                          "stamp": stamp, "file": os.path.basename(original or path)}
    return sorted(best.values(), key=lambda item: -item["stamp"])


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
        print("  7. 支线：%s" % ("开启" if cfg["modules"]["quest"] else "关闭"))
        print("  8. 重新设置解密存档目录")
        print("  9. 选择存档角色：%s" % (cfg.get("save_file") or "自动跟随最近存档"))
        print("  0. 保存并退出")
        choice = input("请选择: ").strip()
        if choice in ("1", "2", "3", "4", "5", "6", "7"):
            name = {"1": "bedroom", "2": "talent", "3": "items", "4": "pill",
                    "5": "forge", "6": "event", "7": "quest"}[choice]
            cfg["modules"][name] = not cfg["modules"][name]
        elif choice == "8":
            path = input("把 BepInEx\\decrypted 的路径粘贴到这里: ").strip().strip('"')
            if os.path.isdir(path):
                cfg["decrypted_dir"] = os.path.normpath(path)
                game = meta_update.game_dir_from_config(cfg, path)
                if game:
                    cfg["game_dir"] = game
            else:
                print("目录不存在，未修改。")
        elif choice == "9":
            options = _character_options(cfg.get("decrypted_dir") or find_dir(cfg, interactive=False))
            if not options:
                print("还没找到可用存档。请先启动游戏，让插件导出存档副本。")
            else:
                print("  0. 自动跟随最近存档")
                for index, item in enumerate(options, 1):
                    when = time.strftime("%m-%d %H:%M", time.localtime(item["stamp"])) if item["stamp"] else "未知"
                    print("  %d. %s · 修炼层数 %s · 奇遇结算 %d 条 · %s" % (
                        index, item["name"], item["layer"], item["settle"], when))
                picked = input("选择角色: ").strip()
                if picked == "0":
                    cfg["save_file"] = ""
                    print("已改为自动跟随最近存档。")
                elif picked.isdigit() and 1 <= int(picked) <= len(options):
                    cfg["save_file"] = options[int(picked) - 1]["file"]
                    print("已固定读取：%s" % options[int(picked) - 1]["name"])
                else:
                    print("输入无效，未修改。")
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
    enabled = _enabled_keys(cfg)
    dec = find_dir(cfg, interactive=bool(enabled))
    opened = False
    last_signature = None
    print("已生成：%s" % OUT_HTML)
    while True:
        try:
            cfg = load_cfg()
            enabled = _enabled_keys(cfg)
            if enabled and (not dec or not os.path.isdir(dec)):
                dec = find_dir(cfg, interactive=last_signature is None)
            signature = state_signature(dec, cfg)
            if signature != last_signature or not os.path.exists(OUT_HTML):
                payload = render(dec, cfg) if dec or not enabled else {
                    "enabled": enabled,
                    "tabs": _enabled_tabs(enabled),
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
