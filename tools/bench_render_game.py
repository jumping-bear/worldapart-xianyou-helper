# -*- coding: utf-8 -*-
"""用"游戏目录里那份真实配置"（16 个模块全开）重测 render/write。"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

GAME_CFG = r"F:\Program Files (x86)\Steam\steamapps\common\A1\BepInEx\仙友助手\config.json"


def main():
    from app import common, registry
    from app.render import render

    cfg = common.load_cfg(GAME_CFG)
    dec = cfg.get("decrypted_dir") or ""
    keys = [k for k, v in cfg["modules"].items() if v]
    specs = registry.active(cfg["modules"])
    modes = {spec.KEY: getattr(spec, "SELECT", "latest") for spec in specs}
    full = {k: v for k, v in modes.items() if v != "latest"}
    print("启用模块 %d 个：%s" % (len(keys), ", ".join(keys)))
    print("需要全量解包（best/merge）的模块：%s" % (full or "无"))
    print("会参与解包的存档份数：%s" % len(common.save_files(dec)))

    for label in ("冷启动", "第二次", "第三次"):
        t0 = time.perf_counter()
        render(dec, cfg)
        print("render %-6s %8.1f ms" % (label, (time.perf_counter() - t0) * 1000))
    return 0


if __name__ == "__main__":
    sys.exit(main())
