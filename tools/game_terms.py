# -*- coding: utf-8 -*-
"""从游戏配置生成界面术语表：同一中文，以游戏官方英文为准。

背景：界面词表（app/i18n.py、i18n_extra.py）是手写的，游戏配置里同一名词有自己的
英文列。两套译名并存时，玩家会看到「Spirit Stones」和「Spirit Stone」两种说法。

做法：取我们词表里的短术语，在配置的中英对照里找同一条目，用游戏的译法覆盖。
只处理「术语型」词条（长度 ≤ 6、无标点、游戏译名 ≤ 3 个词），整句文案不动。

用法：
    python tools/game_terms.py            # 打印差异清单
    python tools/game_terms.py --write     # 改写 app/i18n.py 里的 _GAME_TERMS 块
    python tools/game_terms.py --check     # 只检查是否与当前块一致（发布前用）
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# 游戏译名会和我们已有的界面用词撞车的，保持现状。
KEEP = {
    "委托",   # 游戏叫 Quest，但「任务」已是 Quest，会混淆
    "金",     # 既可能是五行之金（Metal）也可能是钱（Gold），语境不足
}
PUNCT = re.compile(r"[，。；：、（）「」·/]")
BLOCK_START = "# ---- 游戏官方术语（由 tools/game_terms.py 生成，勿手改） ----"
BLOCK_END = "# ---- 游戏官方术语结束 ----"


def _glossary():
    """返回 (简中→英文, 简中集合)：只收英文非空且不含中文的条目。"""
    import meta_update as M

    cfg_path = os.path.join(ROOT, "config.json")
    game = ""
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8-sig") as fh:
                game = json.load(fh).get("game_dir") or ""
        except Exception:
            game = ""
    if not game or not os.path.isdir(game):
        raise SystemExit("找不到游戏目录（config.json 的 game_dir），无法生成术语表")

    tables = M._extract_tables(M.inspect_game(game))
    pairs = {}

    def walk(value):
        if isinstance(value, dict):
            if "zh-Hans" in value or "en-US" in value:
                zh = str(value.get("zh-Hans") or "").strip()
                en = str(value.get("en-US") or "").strip()
                if zh and en and zh != en and not re.search(r"[\u4e00-\u9fff]", en):
                    pairs.setdefault(zh, en)
                return
            for child in value.values():
                walk(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child)

    for table in tables.values():
        walk(table)
    return pairs


def compute():
    """返回需要覆盖的 {中文: 游戏英文}。"""
    from app import i18n

    # 用「手写词表」比较，不要用已经叠了官方术语的 terms()，否则生成器不幂等。
    terms = dict(i18n._EXTRA)
    terms.update(i18n.EN)
    pairs = _glossary()
    out = {}
    for zh, ours in terms.items():
        if zh in KEEP or zh not in pairs:
            continue
        game = pairs[zh]
        if game == ours:
            continue
        if len(zh) > 6 or PUNCT.search(zh):
            continue
        if len(game.split()) > 3:
            continue
        out[zh] = game
    return out


def render_block(mapping):
    lines = [BLOCK_START, "_GAME_TERMS = {"]
    items = sorted(mapping.items())
    for i in range(0, len(items), 3):
        chunk = ", ".join("%r: %r" % (zh, en) for zh, en in items[i:i + 3])
        lines.append("    %s," % chunk.replace("'", '"'))
    lines.append("}")
    lines.append(BLOCK_END)
    return "\n".join(lines)


def current_block(text):
    start = text.find(BLOCK_START)
    end = text.find(BLOCK_END)
    if start < 0 or end < 0:
        return ""
    return text[start:end + len(BLOCK_END)]


def main(argv):
    mapping = compute()
    if "--write" in argv:
        path = os.path.join(ROOT, "app", "i18n.py")
        text = open(path, encoding="utf-8-sig").read()
        block = render_block(mapping)
        old = current_block(text)
        if not old:
            raise SystemExit("app/i18n.py 里找不到 _GAME_TERMS 块标记，请先手工放好空块")
        open(path, "w", encoding="utf-8", newline="").write(text.replace(old, block))
        print("已写入 %d 条游戏官方术语" % len(mapping))
        return
    if "--check" in argv:
        path = os.path.join(ROOT, "app", "i18n.py")
        text = open(path, encoding="utf-8-sig").read()
        same = current_block(text) == render_block(mapping)
        print("术语块与游戏配置%s" % ("一致" if same else "不一致，请跑 --write"))
        raise SystemExit(0 if same else 1)
    print("需要覆盖 %d 条：" % len(mapping))
    for zh, en in sorted(mapping.items()):
        print("  %-8s → %s" % (zh, en))


if __name__ == "__main__":
    main(sys.argv[1:])
