# -*- coding: utf-8 -*-
"""不问凡尘 · 寝室触摸视频进度查询（无需安装 Python 依赖）

1. 安装 BepInEx 插件并把存档解密副本生成到 BepInEx\\decrypted
2. 双击本程序 / 运行 exe，会在同目录生成「进度.html」并自动打开
"""
import glob
import html
import json
import os
import struct
import sys
import time
import webbrowser

FROZEN = getattr(sys, "frozen", False)
HERE = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "config.json")
META = os.path.join(HERE, "bedroom_meta.json")
OUT_HTML = os.path.join(HERE, "进度.html")


# ---------------- MessagePack 解码（最小实现） ----------------
class Ext:
    __slots__ = ("type", "data")

    def __init__(self, t, d):
        self.type, self.data = t, d


def _dec(b, i):
    c = b[i]
    i += 1
    if c <= 0x7F:
        return c, i
    if c >= 0xE0:
        return c - 0x100, i
    if 0x80 <= c <= 0x8F:
        return _map(b, i, c & 0x0F)
    if 0x90 <= c <= 0x9F:
        return _arr(b, i, c & 0x0F)
    if 0xA0 <= c <= 0xBF:
        n = c & 0x1F
        return b[i:i + n].decode("utf-8", "replace"), i + n
    if c == 0xC0:
        return None, i
    if c == 0xC2:
        return False, i
    if c == 0xC3:
        return True, i
    if c in (0xC4, 0xD9):
        n = b[i]
        i += 1
        v = b[i:i + n] if c == 0xC4 else b[i:i + n].decode("utf-8", "replace")
        return v, i + n
    if c in (0xC5, 0xDA):
        n = struct.unpack_from(">H", b, i)[0]
        i += 2
        v = b[i:i + n] if c == 0xC5 else b[i:i + n].decode("utf-8", "replace")
        return v, i + n
    if c in (0xC6, 0xDB):
        n = struct.unpack_from(">I", b, i)[0]
        i += 4
        v = b[i:i + n] if c == 0xC6 else b[i:i + n].decode("utf-8", "replace")
        return v, i + n
    if c == 0xCA:
        return struct.unpack_from(">f", b, i)[0], i + 4
    if c == 0xCB:
        return struct.unpack_from(">d", b, i)[0], i + 8
    if c == 0xCC:
        return b[i], i + 1
    if c == 0xCD:
        return struct.unpack_from(">H", b, i)[0], i + 2
    if c == 0xCE:
        return struct.unpack_from(">I", b, i)[0], i + 4
    if c == 0xCF:
        return struct.unpack_from(">Q", b, i)[0], i + 8
    if c == 0xD0:
        return struct.unpack_from(">b", b, i)[0], i + 1
    if c == 0xD1:
        return struct.unpack_from(">h", b, i)[0], i + 2
    if c == 0xD2:
        return struct.unpack_from(">i", b, i)[0], i + 4
    if c == 0xD3:
        return struct.unpack_from(">q", b, i)[0], i + 8
    if c in (0xD4, 0xD5, 0xD6, 0xD7, 0xD8):
        n = {0xD4: 1, 0xD5: 2, 0xD6: 4, 0xD7: 8, 0xD8: 16}[c]
        return Ext(b[i], b[i + 1:i + 1 + n]), i + 1 + n
    if c in (0xC7, 0xC8, 0xC9):
        n = {0xC7: b[i], 0xC8: struct.unpack_from(">H", b, i)[0], 0xC9: struct.unpack_from(">I", b, i)[0]}[c]
        off = {0xC7: 1, 0xC8: 2, 0xC9: 4}[c]
        t = b[i + off]
        s = i + off + 1
        return Ext(t, b[s:s + n]), s + n
    if c == 0xDC:
        return _arr(b, i + 2, struct.unpack_from(">H", b, i)[0])
    if c == 0xDD:
        return _arr(b, i + 4, struct.unpack_from(">I", b, i)[0])
    if c == 0xDE:
        return _map(b, i + 2, struct.unpack_from(">H", b, i)[0])
    if c == 0xDF:
        return _map(b, i + 4, struct.unpack_from(">I", b, i)[0])
    raise ValueError("msgpack 0x%02x" % c)


def _arr(b, i, n):
    out = []
    for _ in range(n):
        v, i = _dec(b, i)
        out.append(v)
    return out, i


def _map(b, i, n):
    out = {}
    for _ in range(n):
        k, i = _dec(b, i)
        v, i = _dec(b, i)
        out[k] = v
    return out, i


def unpack(data):
    return _dec(data, 0)[0]


# ---------------- 数据层 ----------------
def load_meta():
    try:
        with open(META, encoding="utf-8-sig") as f:
            return {int(r["cfg"]): r for r in json.load(f)}
    except Exception:
        return {}


def save_cfg(p):
    try:
        with open(CFG, "w", encoding="utf-8") as f:
            json.dump({"decrypted_dir": p}, f, ensure_ascii=False)
    except Exception:
        pass


def find_dir():
    if os.path.exists(CFG):
        try:
            with open(CFG, encoding="utf-8") as f:
                p = json.load(f).get("decrypted_dir", "")
            if p and os.path.isdir(p):
                return p
        except Exception:
            pass
    for c in [os.path.join(HERE, "decrypted"),
              os.path.join(HERE, "..", "BepInEx", "decrypted")] + [
                 d + r"\BepInEx\decrypted"
                 for d in ("C:", "D:", "E:", "F:", "G:")]:
        if os.path.isdir(c) and glob.glob(os.path.join(c, "*gameworld*")):
            save_cfg(c)
            return c
    print("没找到解密存档目录。请先安装插件并启动一次游戏。")
    p = input("把 BepInEx\\decrypted 的路径粘贴到这里: ").strip().strip('"')
    if os.path.isdir(p):
        save_cfg(p)
        return p
    return None


def scan(path, meta):
    obj = unpack(open(path, "rb").read())
    rows = []
    for n in (obj.get("npcs") or {}).values():
        b = n.get("bedroom") or {}
        cfg = n.get("npcCfgId")
        info = meta.get(cfg) or {}
        unlocked = b.get("unlocked") or []
        acts = [a["id"] for a in (info.get("actions") or [])][:3]
        if not acts:
            acts = sorted(unlocked)[:3]
        if not acts:
            continue
        labels = {a["id"]: a.get("label") or a.get("slot") or str(a["id"])
                  for a in (info.get("actions") or [])}
        ctf = b.get("completed_touch_feedbacks") or {}
        parts = []
        total = 0
        for a in acts:
            got = sorted(v for v in ctf.get(a, []) if 0 <= v <= 5)
            total += len(got)
            parts.append({"id": a, "label": labels.get(a, str(a)),
                          "got": got, "miss": [i for i in range(6) if i not in got]})
        rows.append({"cfg": cfg, "who": info.get("npcName") or ("#%s" % cfg),
                     "bed": info.get("bedroom") or "", "total": total, "parts": parts,
                     "resident": len(unlocked) >= 3})
    rows.sort(key=lambda r: (-r["total"], r["who"]))
    return rows


# ---------------- HTML ----------------
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0e1014;color:#e8eaed;font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif;padding:28px 20px 60px}
.wrap{max-width:1080px;margin:0 auto}
h1{font-size:22px;font-weight:600;letter-spacing:.5px}
.sub{color:#8b93a1;font-size:13px;margin-top:6px}
.cards{display:flex;gap:14px;flex-wrap:wrap;margin:20px 0 26px}
.card{background:#171a21;border:1px solid #232833;border-radius:12px;padding:14px 18px;min-width:150px}
.card .k{color:#8b93a1;font-size:12px}
.card .v{font-size:22px;font-weight:600;margin-top:4px}
.card .v span{font-size:13px;color:#8b93a1;font-weight:400}
table{width:100%;border-collapse:separate;border-spacing:0 8px}
th{text-align:left;color:#7d8593;font-size:12px;font-weight:500;padding:0 12px}
td{background:#15181f;padding:12px;vertical-align:middle}
tr.row td:first-child{border-radius:10px 0 0 10px}
tr.row td:last-child{border-radius:0 10px 10px 0}
.who{font-size:15px;font-weight:600}
.bed{color:#7d8593;font-size:12px;margin-top:3px}
.parts{display:flex;gap:26px;flex-wrap:wrap}
.part .pl{color:#9aa3b2;font-size:12px;margin-bottom:6px}
.dots{display:flex;gap:4px}
.dot{width:18px;height:18px;border-radius:5px;background:#252b36;display:flex;align-items:center;justify-content:center;font-size:10px;color:#5d6675}
.dot.on{background:#2f7d54;color:#c9f5dd}
.dot.miss{background:#3a2126;color:#a45d6b}
.bar{height:6px;border-radius:3px;background:#232833;overflow:hidden;margin-top:8px}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#3ddc84,#2f9e6b)}
.pct{font-variant-numeric:tabular-nums;font-weight:600;font-size:15px;text-align:right}
.pct small{display:block;color:#7d8593;font-weight:400;font-size:11px;margin-top:2px}
.full{color:#3ddc84}
.badge{display:inline-block;margin-left:6px;padding:1px 6px;border-radius:6px;background:#242a34;color:#7d8593;font-size:10px;font-weight:400;vertical-align:middle}
.tip{margin-top:26px;color:#6f7787;font-size:12px;line-height:1.9}
"""


def build_html(rows, src, stamp, meta):
    done = sum(1 for r in rows if r["total"] >= 18)
    goals = [(1, "十八摸Ⅰ"), (3, "十八摸Ⅱ"), (5, "十八摸Ⅲ"), (10, "十八摸Ⅳ")]
    cards = ['<div class="card"><div class="k">已完成 18/18</div><div class="v">%d <span>位</span></div></div>' % done]
    for n, name in goals:
        cards.append('<div class="card"><div class="k">%s</div><div class="v">%s</div></div>'
                     % (name, "已达成" if done >= n else "还差 %d 位" % (n - done)))

    trs = []
    for r in rows:
        parts = []
        for p in r["parts"]:
            dots = "".join('<i class="dot %s">%d</i>' % ("on" if i in p["got"] else "miss", i)
                           for i in range(6))
            parts.append('<div class="part"><div class="pl">%s</div><div class="dots">%s</div></div>'
                         % (html.escape(p["label"]), dots))
        pct = min(100, int(r["total"] * 100 / 18))
        cls = "full" if r["total"] >= 18 else ""
        badge = "" if r.get("resident") else '<span class="badge">未入住</span>'
        trs.append(
            '<tr class="row"><td><div class="who">%s%s</div><div class="bed">%s</div></td>'
            '<td><div class="parts">%s</div></td>'
            '<td style="width:150px"><div class="pct %s">%d/18<small>%s</small></div>'
            '<div class="bar"><i style="width:%d%%"></i></div></td></tr>'
            % (html.escape(str(r["who"])), badge, html.escape(r["bed"]), "".join(parts),
               cls, r["total"], "已完成" if r["total"] >= 18 else "进行中", pct))

    body = ('<div class="wrap"><h1>寝室触摸视频 · 收集进度</h1>'
            '<div class="sub">存档：%s ｜ 更新：%s ｜ 共 %d 位仙友</div>'
            '<div class="cards">%s</div>'
            '<table><thead><tr><th>仙友 / 寝室</th><th>各部位 6 段</th><th></th></tr></thead>'
            '<tbody>%s</tbody></table>'
            '<div class="tip">每个部位 6 段：0~3 为四段升阶，4 为循环段，5 为回落段。'
            '缺段常见于 2（第三段，点太快会跳过）与 5（需停手等回落）。<br>'
            '只有入住小重天的仙友才会记录；18/18 才算 1 位，成就按位数统计。</div></div>'
            % (html.escape(src), html.escape(stamp), len(rows), "".join(cards), "".join(trs)))
    return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta http-equiv="refresh" content="3">'
            '<title>寝室触摸进度</title><style>%s</style></head><body>%s</body></html>'
            % (CSS, body))


def signature(dec):
    best = 0.0
    try:
        for f in glob.glob(os.path.join(dec, "*gameworld*")):
            try:
                best = max(best, os.path.getmtime(f))
            except Exception:
                pass
    except Exception:
        pass
    return best


def render(dec, meta):
    files = [f for f in glob.glob(os.path.join(dec, "*gameworld*")) if os.path.getsize(f) > 100000]
    if not files:
        return None
    best = None
    for f in files:
        try:
            rows = scan(f, meta)
        except Exception:
            continue
        score = sum(r["total"] for r in rows)
        if best is None or score > best[0]:
            best = (score, f, rows)
    if best is None:
        return None
    _, path, rows = best
    stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(build_html(rows, os.path.basename(path), stamp, meta))
    return rows, path, stamp


def console(rows):
    print("%-10s %-10s %-7s %s" % ("仙友", "寝室", "进度", "缺的段"))
    print("-" * 62)
    for r in rows:
        miss = "  ".join("%s:%s" % (p["label"], ",".join(map(str, p["miss"])) or "满")
                         for p in r["parts"])
        print("%-10s %-10s %2d/18   %s" % (r["who"], r["bed"], min(r["total"], 18), miss))
    print("-" * 62)
    print("已满 18/18：%d 位" % sum(1 for r in rows if r["total"] >= 18))


def main():
    if FROZEN:
        try:
            os.system("chcp 65001 >nul")
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    dec = find_dir()
    if not dec:
        if FROZEN:
            input("按回车退出...")
        return
    meta = load_meta()
    out = render(dec, meta)
    if not out:
        print("还没有可用存档副本，请先启动一次游戏（插件会自动生成）。")
        if FROZEN:
            input("按回车退出...")
        return
    rows, path, stamp = out
    console(rows)
    print("\n已生成：%s" % OUT_HTML)
    try:
        webbrowser.open("file:///" + OUT_HTML.replace("\\", "/"))
    except Exception:
        pass

    if "--once" in sys.argv:
        if FROZEN:
            input("按回车退出...")
        return

    print("监视中：游戏内按 F8 或自动同步后，网页几秒内自动更新（Ctrl+C 结束）")
    last = signature(dec)
    try:
        while True:
            time.sleep(3)
            sig = signature(dec)
            if sig == last:
                continue
            last = sig
            out2 = render(dec, meta)
            if out2:
                print("[%s] 数据已更新" % time.strftime("%H:%M:%S"))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("监视结束：", e)


if __name__ == "__main__":
    main()
