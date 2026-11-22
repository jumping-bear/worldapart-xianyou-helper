# -*- coding: utf-8 -*-
"""拆解 render 的 1.1 秒花在哪：读盘 / msgpack 解码 / 模块计算。"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main():
    from app import common
    import meta_update

    cfg = common.load_cfg()
    dec = cfg.get("decrypted_dir") or ""
    files = common.save_files(dec)
    print("存档副本 %d 份" % len(files))

    # 单份：读盘 vs 解码
    sample = max(files, key=os.path.getsize)
    size_mb = os.path.getsize(sample) / 1048576.0

    t0 = time.perf_counter()
    with open(sample, "rb") as fh:
        raw = fh.read()
    t_read = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    obj = meta_update.unpack(raw)
    t_unpack = (time.perf_counter() - t0) * 1000
    print("单份 %.1f MB：读盘 %6.1f ms，msgpack 解码 %6.1f ms" % (size_mb, t_read, t_unpack))

    # 全部读一遍 + 解一遍，估算下限
    t0 = time.perf_counter()
    for p in files:
        with open(p, "rb") as fh:
            meta_update.unpack(fh.read())
    t_all = (time.perf_counter() - t0) * 1000
    print("全部 %d 份都读+解码：%8.1f ms（这是 render 的物理下限）" % (len(files), t_all))

    # render：冷 / 热
    from app.render import render
    for label in ("冷启动", "第二次（缓存已热）", "第三次"):
        t0 = time.perf_counter()
        render(dec, cfg)
        print("render %-16s %8.1f ms" % (label, (time.perf_counter() - t0) * 1000))
    return 0


if __name__ == "__main__":
    sys.exit(main())
