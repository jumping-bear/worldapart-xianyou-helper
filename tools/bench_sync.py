# -*- coding: utf-8 -*-
"""实测助手同步链路的真实耗时：stat 轮询 / render / 写页面。

目的：找出"存档同步时卡"到底卡在哪一步，而不是凭猜。
只读存档副本，页面写到临时目录，不改动仓库与游戏。
"""
import os
import sys
import tempfile
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def ms(fn, *a, **kw):
    t0 = time.perf_counter()
    result = fn(*a, **kw)
    return (time.perf_counter() - t0) * 1000.0, result


def main():
    from app import common
    from app.output import write_outputs, _atomic_text
    from app.render import render

    cfg = common.load_cfg()
    dec = cfg.get("decrypted_dir") or ""
    print("解密存档目录：%s" % dec)
    if not dec or not os.path.isdir(dec):
        print("目录不可用，退出")
        return 1

    files = common.save_files(dec)
    total = sum(os.path.getsize(p) for p in files)
    print("存档副本：%d 份，合计 %.1f MB" % (len(files), total / 1048576.0))

    # 1) 轮询开销：watch() 每 2.5 秒做的事
    t, sig = ms(common.state_signature, dec, cfg)
    print("\n[1] state_signature（每 2.5 秒一次）：      %8.2f ms" % t)

    # 2) 渲染：真正读存档、算 20 个模块
    t, payload = ms(render, dec, cfg)
    print("[2] render（有新存档时触发）：            %8.2f ms" % t)

    # 3) 写页面：9.6MB HTML + 版本 JS（含 fsync）
    out_dir = tempfile.mkdtemp(prefix="xy_bench_")
    common.set_output_dir(out_dir)
    t, (version, changed) = ms(write_outputs, payload)
    size = os.path.getsize(common.OUT_HTML) / 1048576.0
    print("[3] write_outputs 首次写入（%.1f MB，含 fsync）： %8.2f ms" % (size, t))

    # 4) 内容没变时：只算哈希，不写盘
    t, (version2, changed2) = ms(write_outputs, payload)
    print("[4] write_outputs 内容未变（跳过写盘）：   %8.2f ms   changed=%s" % (t, changed2))

    # 5) 单独测 fsync 成本
    probe = os.path.join(out_dir, "probe.txt")
    text = "x" * (10 * 1024 * 1024)
    t, _ = ms(_atomic_text, probe, text)
    print("[5] 单独写 10MB + fsync：                  %8.2f ms" % t)

    # 6) 同步一次的总和（游戏里点「立即同步」到页面刷新）
    print("\n合计（有新存档时一次完整同步）：            %8.2f ms" % (t_total(payload, dec, cfg, out_dir)))
    print("临时输出目录：%s" % out_dir)
    return 0


def t_total(payload, dec, cfg, out_dir):
    from app import common
    from app.output import write_outputs
    from app.render import render
    t_all = 0.0
    for _ in range(3):
        a = time.perf_counter()
        p = render(dec, cfg)
        write_outputs(p)
        t_all += (time.perf_counter() - a) * 1000.0
    return t_all / 3.0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
