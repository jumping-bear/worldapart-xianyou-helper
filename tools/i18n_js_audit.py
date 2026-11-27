# -*- coding: utf-8 -*-
"""检查英文界面里「JS 硬编码文案」的中文残留。

DATA 数据由 tools/i18n_audit.py 负责；这里补另一半：模块 view.js 与页面模板里的
placeholder、title、按钮、空态、提示句。这些运行时由 MutationObserver 的
localize() 走 trText 翻译，因此必须用同一套 trText 复现，不能只看源码。

注意：JS 模板字符串常包含整段 HTML，运行时翻译的是 DOM 文本节点而不是整串，
所以这里先剥掉标签与 ${...}，按「可见文本片段」逐个检查。

用法：python tools/i18n_js_audit.py <英文页.html> [--json out.json]
"""
import importlib.util
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CJK = re.compile(r"[\u4e00-\u9fff]")
LITERAL = re.compile(r"""'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"|`[^`]*`""", re.S)
TAG = re.compile(r"<[^>]*>")


def load_spans():
    path = os.path.join(ROOT, "tools", "i18n_audit.py")
    spec = importlib.util.spec_from_file_location("ia", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.spans()


def source_texts():
    texts = []
    for name in sorted(os.listdir(os.path.join(ROOT, "app", "modules"))):
        path = os.path.join(ROOT, "app", "modules", name, "view.js")
        if os.path.isfile(path):
            texts.append(open(path, encoding="utf-8-sig").read())
    out = open(os.path.join(ROOT, "app", "output.py"), encoding="utf-8-sig").read()
    start = out.index("const INITIAL_VERSION=")
    end = out.index("</script></body></html>", start)
    template = out[start:end]
    # 翻译规则数组里的中文是「模式」，不是显示文案，排除
    template = re.sub(r"const TR_FIRST=\[.*?\nconst TR_CJK=", "const TR_CJK=",
                      template, count=1, flags=re.S)
    texts.append(template)
    return "\n".join(texts)


def visible_fragments():
    src = source_texts()
    raw = LITERAL.findall(src)
    # 模板字符串里嵌套的 '中文' 也要单独看
    nested = []
    for lit in raw:
        nested.extend(LITERAL.findall(lit[1:-1]))
    out = []
    for lit in raw + nested:
        body = lit[1:-1]
        if not CJK.search(body) or len(body) > 400:
            continue
        body = body.replace("\\'", "'").replace('\\"', '"').replace("\\n", " ")
        body = TAG.sub("\n", body)
        for piece in body.split("\n"):
            piece = re.sub(r"\$\{[^}]*\}", "1", piece).strip()
            if piece and CJK.search(piece) and len(piece) <= 120:
                out.append(piece)
    return list(dict.fromkeys(out))


def main():
    html = sys.argv[1]
    frags = visible_fragments()
    first, last_rules, rules, tail = load_spans()
    h = open(html, encoding="utf-8-sig").read()
    i = h.index("const DATA=") + len("const DATA=")
    payload, _ = json.JSONDecoder().raw_decode(h[i:])
    en = payload.get("i18n") or {}

    js = "\n".join([
        "const LANG='en';",
        "const DATA=%s;" % json.dumps({"i18n": en}, ensure_ascii=False),
        "const EN=DATA.i18n;",
        first, last_rules, rules, tail,
        "const cjk=/[\\u4e00-\\u9fff]/;",
        "const items=%s;" % json.dumps(frags, ensure_ascii=False),
        "const out=[];items.forEach(t=>{const r=trText(t);if(cjk.test(r))out.push([t,r])});",
        "process.stdout.write(JSON.stringify(out));",
    ])
    harness = os.path.join(ROOT, "tmp", "_js_tr_harness.js")
    open(harness, "w", encoding="utf-8").write(js)
    proc = subprocess.run(["node", harness], capture_output=True, text=True, encoding="utf-8")
    if proc.returncode:
        raise SystemExit(proc.stderr[:1000])
    left = json.loads(proc.stdout)
    uniq = {}
    for src, translated in left:
        uniq.setdefault(src, translated)
    print("界面可见文案 %d 条；trText 后仍含中文 %d 条" % (len(frags), len(uniq)))
    for src, translated in uniq.items():
        print("   %-46s -> %s" % (src[:46], translated[:48]))
    if "--json" in sys.argv:
        path = sys.argv[sys.argv.index("--json") + 1]
        json.dump(uniq, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\n已写出 %s" % path)


if __name__ == "__main__":
    main()
