# -*- coding: utf-8 -*-
"""抽取页面里的翻译 JS，用 node 复现「英文模式玩家实际看到什么」。

用法：python tmp/i18n_audit.py <html> [out.json]
输出：仍含中文的字符串（按出现次数排序），以及导出给 node 的脚本 tmp/_tr_harness.js
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "app", "output.py")


def spans():
    src = open(OUT, encoding="utf-8-sig").read()

    def block(start_marker, stop_marker):
        i = src.index(start_marker)
        j = src.index(stop_marker, i)
        return src[i:j]

    first = block("const TR_FIRST=[", "const TR_LAST=[")
    last_rules = block("const TR_LAST=[", "const TR_RULES=[")
    rules = block("const TR_RULES=[", "\nconst TR_CJK")
    tail_start = src.index("const TR_CJK")
    tail = src[tail_start:src.index("\nfunction localize(", tail_start)]
    return first, last_rules, rules, tail


def build(html_path):
    html = open(html_path, encoding="utf-8-sig").read()
    i = html.index("const DATA=") + len("const DATA=")
    data, _ = json.JSONDecoder().raw_decode(html[i:])
    first, last_rules, rules, tail = spans()
    js = "\n".join([
        "const LANG='en';",
        "const DATA=%s;" % json.dumps({"i18n": data["i18n"]}, ensure_ascii=False),
        "const EN=DATA.i18n;",
        first, last_rules, rules, tail,
        "const cjk=/[\\u4e00-\\u9fff]/;",
        "const out={};",
        "const walk=(v,p)=>{",
        "  if(typeof v==='string'){",
        "    if(!cjk.test(v))return;",
        "    const t=trText(v);",
        "    if(cjk.test(t)){(out[p]||(out[p]=[])).push([v,t])}",
        "  }else if(Array.isArray(v)){v.forEach(x=>walk(x,p))}",
        "  else if(v&&typeof v==='object'){for(const k in v)walk(v[k],k)}",
        "};",
        "walk(%s,'');" % json.dumps(data, ensure_ascii=False),
        "process.stdout.write(JSON.stringify(out));",
    ])
    path = os.path.join(ROOT, "tmp", "_tr_harness.js")
    open(path, "w", encoding="utf-8").write(js)
    res = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8")
    if res.returncode:
        raise SystemExit(res.stderr[:2000])
    return json.loads(res.stdout)


def main():
    html = sys.argv[1]
    left = build(html)
    total = sum(len(v) for v in left.values())
    print("英文模式仍含中文的字符串：%d 条\n" % total)
    rows = sorted(((k, v) for k, v in left.items()), key=lambda kv: -len(kv[1]))
    for key, items in rows[:14]:
        print("[%s] %d 条" % (key, len(items)))
        seen = set()
        for src, out in items:
            if src in seen:
                continue
            seen.add(src)
            print("   %-38s -> %s" % (src[:38], out[:44]))
            if len(seen) >= 4:
                break
    if len(sys.argv) > 2:
        json.dump({k: v for k, v in left.items()}, open(sys.argv[2], "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("\n明细已写入 %s" % sys.argv[2])


if __name__ == "__main__":
    main()
