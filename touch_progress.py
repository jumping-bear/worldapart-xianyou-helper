# -*- coding: utf-8 -*-
"""不问凡尘 · 仙友助手：十八摸与 NPC 天赋只读查询。"""
import glob
import hashlib
import html
import json
import os
import re
import struct
import sys
import time
import webbrowser

import meta_update

FROZEN = getattr(sys, "frozen", False)
HERE = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
BUILTIN_DIR = getattr(sys, "_MEIPASS", HERE)
CFG = os.path.join(HERE, "config.json")
OUT_HTML = os.path.join(HERE, "仙友助手.html")
OUT_VERSION = os.path.join(HERE, "仙友助手版本.js")
DEFAULT_MODULES = {"bedroom": True, "talent": True, "items": True}


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
    if c in (0xC2, 0xC3):
        return c == 0xC3, i
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


# ---------------- 配置与存档定位 ----------------
def load_cfg():
    raw = meta_update._read_json(CFG, {}) or {}
    modules = raw.get("modules") if isinstance(raw.get("modules"), dict) else {}
    return {
        "decrypted_dir": str(raw.get("decrypted_dir") or ""),
        "game_dir": str(raw.get("game_dir") or ""),
        "modules": {name: bool(modules.get(name, default)) for name, default in DEFAULT_MODULES.items()},
    }


def save_cfg(cfg):
    data = {
        "decrypted_dir": cfg.get("decrypted_dir", ""), "game_dir": cfg.get("game_dir", ""),
        "modules": {name: bool((cfg.get("modules") or {}).get(name, default))
                    for name, default in DEFAULT_MODULES.items()},
    }
    try:
        meta_update._atomic_json(CFG, data)
        return True
    except Exception as e:
        print("配置保存失败：%s" % e)
        return False


def find_dir(cfg, interactive=True):
    configured = cfg.get("decrypted_dir") or ""
    if configured and os.path.isdir(configured):
        return configured
    candidates = [os.path.join(HERE, "decrypted"), os.path.join(HERE, "..", "BepInEx", "decrypted")]
    candidates += [d + r"\BepInEx\decrypted" for d in ("C:", "D:", "E:", "F:", "G:")]
    for candidate in candidates:
        if os.path.isdir(candidate) and glob.glob(os.path.join(candidate, "*gameworld*")):
            cfg["decrypted_dir"] = os.path.normpath(candidate)
            save_cfg(cfg)
            return cfg["decrypted_dir"]
    if not interactive:
        return ""
    print("没找到解密存档目录。请先安装插件并启动一次游戏。")
    path = input("把 BepInEx\\decrypted 的路径粘贴到这里: ").strip().strip('"')
    if os.path.isdir(path):
        cfg["decrypted_dir"] = os.path.normpath(path)
        save_cfg(cfg)
        return cfg["decrypted_dir"]
    return ""


def find_save_root():
    local_low = os.path.expanduser(r"~\AppData\LocalLow")
    candidates = glob.glob(os.path.join(local_low, "*", "*", "StorageV1", "1.0"))
    for candidate in candidates:
        if glob.glob(os.path.join(candidate, "*", "slots", "*", "gameworld.msgpack")):
            return candidate
    return ""


def original_save_index(save_root):
    index = {}
    if not save_root:
        return index
    for path in glob.glob(os.path.join(save_root, "*", "slots", "*", "gameworld.msgpack")):
        rel = os.path.relpath(path, save_root).replace("\\", "_").replace("/", "_") + ".bin"
        index[rel] = path
    return index


def source_time(copy_path, originals):
    original = originals.get(os.path.basename(copy_path))
    path = original if original and os.path.isfile(original) else copy_path
    try:
        return os.path.getmtime(path), original or ""
    except OSError:
        return 0.0, original or ""


def save_files(dec):
    files = []
    for path in glob.glob(os.path.join(dec, "*gameworld*")):
        try:
            if os.path.getsize(path) > 100000:
                files.append(path)
        except OSError:
            pass
    return files


def state_signature(dec, cfg):
    result = []
    for path in save_files(dec) if dec else []:
        try:
            stat = os.stat(path)
            result.append((os.path.basename(path), stat.st_mtime_ns, stat.st_size))
        except OSError:
            pass
    try:
        cfg_stamp = os.stat(CFG).st_mtime_ns
    except OSError:
        cfg_stamp = 0
    return tuple(sorted(result)), cfg_stamp, tuple(sorted(k for k, v in cfg["modules"].items() if v))


# ---------------- 数据扫描 ----------------
def scan_bedroom(obj, meta):
    rows = []
    for npc in (obj.get("npcs") or {}).values():
        if not isinstance(npc, dict):
            continue
        bedroom = npc.get("bedroom") or {}
        cfg = npc.get("npcCfgId")
        info = meta.get(cfg) or {}
        unlocked = bedroom.get("unlocked") or []
        actions = [a["id"] for a in (info.get("actions") or []) if a.get("id") is not None][:3]
        if not actions:
            try:
                actions = sorted(unlocked)[:3]
            except TypeError:
                actions = []
        if not actions:
            continue
        labels = {a["id"]: a.get("label") or a.get("slot") or str(a["id"])
                  for a in (info.get("actions") or []) if a.get("id") is not None}
        completed = bedroom.get("completed_touch_feedbacks") or {}
        parts, total = [], 0
        for action in actions:
            got = sorted(v for v in (completed.get(action) or []) if isinstance(v, int) and 0 <= v <= 5)
            total += len(got)
            parts.append({"id": action, "label": labels.get(action, str(action)), "got": got,
                          "miss": [i for i in range(6) if i not in got]})
        rows.append({"cfg": cfg, "who": info.get("npcName") or ("#%s" % cfg),
                     "bed": info.get("bedroom") or "", "total": total, "parts": parts,
                     "resident": len(unlocked) >= 3})
    rows.sort(key=lambda r: (-r["total"], str(r["who"])))
    return rows


def scan(path, meta):
    """兼容旧调用：读取一个副本并返回十八摸进度。"""
    with open(path, "rb") as f:
        return scan_bedroom(unpack(f.read()), meta)


def scan_talent(obj, meta):
    talents = {str(r.get("id")): r for r in meta.get("talents", []) if isinstance(r, dict)}
    npc_meta = meta.get("npcs") or {}
    space_meta = meta.get("spaces") or {}
    spaces = obj.get("spaces") or {}
    player = obj.get("playerModel") or {}
    dao_ids = {str(x) for x in ((player.get("npc_dao_ally") or {}).get("npc_ids") or [])}
    rows = []
    for uid, npc in (obj.get("npcs") or {}).items():
        if not isinstance(npc, dict):
            continue
        saved_slots = (npc.get("talent") or {}).get("slots") or []
        if not saved_slots:
            continue
        cfg = npc.get("npcCfgId")
        info = npc_meta.get(str(cfg)) or {}
        slot_info = {str(s.get("slot_id")): s for s in info.get("slots", []) if isinstance(s, dict)}
        slots = []
        for saved in saved_slots:
            if not isinstance(saved, dict):
                continue
            talent_id = saved.get("talent_id")
            extra = slot_info.get(str(saved.get("slot_id"))) or {}
            talent = talents.get(str(talent_id)) or {}
            slots.append({
                "slot_id": saved.get("slot_id"), "talent_id": talent_id,
                "unlocked": bool(saved.get("unlocked")),
                "required_realm": extra.get("required_npc_realm_id", 0),
                "conditions": extra.get("unlock_conditions") or [],
                "known": bool(talent),
            })
        space = spaces.get(npc.get("currentSpaceUuid")) or {}
        space_id = space.get("spaceId")
        space_info = space_meta.get(str(space_id)) or {}
        location = space_info.get("name") or "未知地点"
        path = space_info.get("path") or [location]
        rows.append({
            "uid": str(uid), "cfg": cfg, "who": info.get("name") or ("#%s" % cfg),
            "title": info.get("title") or "", "location": location,
            "region": space_info.get("region") or location,
            "location_path": " / ".join(path), "space_id": space_id,
            "dao": str(cfg) in dao_ids, "slots": slots,
        })
    rows.sort(key=lambda r: (str(r["who"]), str(r["uid"])))
    return rows


def bag_items(bag):
    """取出背包持有关系 [(item_id, count)]，兼容列表与字典两种存档形态。"""
    entries = bag.get("items") if isinstance(bag, dict) else bag
    result = []
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2 and isinstance(entry[1], dict):
                entry = entry[1]
            if not isinstance(entry, dict):
                continue
            item_id = entry.get("item_id", entry.get("itemId", entry.get("id")))
            if item_id is None:
                continue
            result.append([item_id, entry.get("count") or entry.get("num") or 1])
    elif isinstance(entries, dict):
        for key, entry in entries.items():
            if isinstance(entry, dict):
                item_id = entry.get("item_id", entry.get("itemId", entry.get("id", key)))
                result.append([item_id, entry.get("count") or entry.get("num") or 1])
            else:
                try:
                    result.append([int(key), int(entry)])
                except (TypeError, ValueError):
                    continue
    return result


def scan_items(obj, meta):
    """收集 NPC 背包持有关系；是否可偷由 NPC 的 can_steal 和物品 steal 参数共同决定。"""
    npc_meta = meta.get("npcs") or {}
    space_meta = meta.get("spaces") or {}
    spaces = obj.get("spaces") or {}
    rows = []
    for uid, npc in (obj.get("npcs") or {}).items():
        if not isinstance(npc, dict):
            continue
        held = bag_items(npc.get("bag"))
        if not held:
            continue
        merged = {}
        for item_id, count in held:
            key = str(item_id)
            merged[key] = merged.get(key, 0) + (count or 1)
        held = [[int(key) if key.isdigit() else key, total] for key, total in merged.items()]
        cfg = npc.get("npcCfgId")
        info = npc_meta.get(str(cfg)) or {}
        space = spaces.get(npc.get("currentSpaceUuid")) or {}
        space_info = space_meta.get(str(space.get("spaceId"))) or {}
        path = space_info.get("path") or []
        location = space_info.get("name") or "未知地点"
        rows.append({
            "uid": str(uid), "cfg": cfg,
            "who": info.get("name") or ("#%s" % cfg),
            "realm": info.get("realm") or "",
            "location": location, "region": space_info.get("region") or "",
            "location_path": " / ".join(path) or location,
            "can_steal": bool(info.get("can_steal")),
            "items": held,
        })
    rows.sort(key=lambda r: (str(r["who"]), str(r["uid"])))
    return rows


def _source_payload(path, stamp, original, rows, meta_info):
    return {
        "rows": rows, "src": os.path.basename(path) if path else "",
        "original": original, "stamp": stamp,
        "stamp_text": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stamp)) if stamp else "未知",
        "config": meta_info.get("label", "未知"),
        "config_warning": meta_info.get("warning", ""),
    }


def render(dec, cfg):
    enabled = [name for name in ("bedroom", "talent", "items") if cfg["modules"].get(name)]
    payload = {"enabled": enabled, "modules": {}, "warnings": []}
    if not enabled:
        payload["warnings"].append("查询模块都已关闭。请运行“功能设置.bat”重新开启。")
        return payload
    game_dir = meta_update.game_dir_from_config(cfg, dec)
    if game_dir and game_dir != cfg.get("game_dir"):
        cfg["game_dir"] = game_dir
        save_cfg(cfg)
    metadata, report = meta_update.load_metadata(game_dir, BUILTIN_DIR, tuple(enabled))
    payload["warnings"].extend(report.get("warnings") or [])
    bedroom_meta = {int(r["cfg"]): r for r in metadata.get("bedroom", [])
                    if isinstance(r, dict) and r.get("cfg") is not None}
    empty = {"items": {}, "npcs": {}, "spaces": {}, "realms": {"0": "凡人"}}
    talent_meta = metadata.get("talent") or dict(empty, talents=[])
    items_meta = metadata.get("items") or dict(empty)
    files = save_files(dec)
    originals = original_save_index(find_save_root())
    timed = [(path,) + source_time(path, originals) for path in files]
    best_bedroom, latest_talent, latest_items = None, None, None
    errors = []

    for path, stamp, original in timed:
        try:
            with open(path, "rb") as f:
                obj = unpack(f.read())
            if not isinstance(obj, dict) or not isinstance(obj.get("npcs"), dict):
                raise ValueError("存档缺少 NPC 数据")
            if "bedroom" in enabled:
                rows = scan_bedroom(obj, bedroom_meta)
                score = sum(r["total"] for r in rows)
                if best_bedroom is None or score > best_bedroom[0]:
                    best_bedroom = (score, _source_payload(
                        path, stamp, original, rows, report["modules"]["bedroom"]))
            if "talent" in enabled and (latest_talent is None or stamp > latest_talent["stamp"]):
                latest_talent = _source_payload(
                    path, stamp, original, scan_talent(obj, talent_meta), report["modules"]["talent"])
            if "items" in enabled and (latest_items is None or stamp > latest_items["stamp"]):
                latest_items = _source_payload(
                    path, stamp, original, scan_items(obj, items_meta), report["modules"]["items"])
        except Exception as e:
            errors.append("%s：%s" % (os.path.basename(path), e))

    if "bedroom" in enabled:
        payload["modules"]["bedroom"] = best_bedroom[1] if best_bedroom else _source_payload(
            "", 0, "", [], report["modules"]["bedroom"])
    if "talent" in enabled:
        module = latest_talent or _source_payload("", 0, "", [], report["modules"]["talent"])
        module["talents"] = talent_meta.get("talents") or []
        module["realms"] = talent_meta.get("realms") or {"0": "凡人"}
        payload["modules"]["talent"] = module
    if "items" in enabled:
        module = latest_items or _source_payload("", 0, "", [], report["modules"]["items"])
        catalog = items_meta.get("items") or {}
        used = {str(item_id) for row in module["rows"] for item_id, _count in row["items"]}
        module["catalog"] = [dict(catalog[key], id=int(key)) for key in sorted(used, key=int)
                             if key in catalog]
        module["realms"] = items_meta.get("realms") or {"0": "凡人"}
        payload["modules"]["items"] = module
    if not files:
        payload["warnings"].append("还没有可用存档副本，请先启动游戏并等待插件导出。")
    elif errors:
        payload["warnings"].append("跳过 %d 份无法解析的副本。" % len(errors))
        payload["errors"] = errors[:5]
    if ("bedroom" in enabled and best_bedroom is None) or \
            (("talent" in enabled and latest_talent is None) or ("items" in enabled and latest_items is None)):
        payload["warnings"].append("暂未找到有效存档，请确认插件已导出 gameworld 副本。")
    return payload


# ---------------- 静态网页 ----------------
CSS = r"""
*{box-sizing:border-box;margin:0;padding:0}body{background:#0e1014;color:#e8eaed;font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif;padding:26px 20px 60px}.wrap{max-width:1180px;margin:0 auto}h1{font-size:23px;font-weight:600;letter-spacing:.5px}.sub,.source{color:#8b93a1;font-size:12px;line-height:1.8}.sub{margin-top:6px}.tabs{display:flex;gap:8px;margin:20px 0 16px}.tab{border:1px solid #29303c;background:#171a21;color:#9aa3b2;border-radius:9px;padding:9px 18px;cursor:pointer;font-size:14px}.tab.active{background:#263b34;border-color:#3d735b;color:#c9f5dd}.panel{display:none}.panel.active{display:block}.source{margin-bottom:14px}.cards{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0 22px}.card{background:#171a21;border:1px solid #232833;border-radius:12px;padding:13px 17px;min-width:145px}.card .k{color:#8b93a1;font-size:12px}.card .v{font-size:21px;font-weight:600;margin-top:4px}.card .v span{font-size:12px;color:#8b93a1;font-weight:400}table{width:100%;border-collapse:separate;border-spacing:0 8px}th{text-align:left;color:#7d8593;font-size:12px;font-weight:500;padding:0 12px}td{background:#15181f;padding:12px;vertical-align:middle}tr.row td:first-child{border-radius:10px 0 0 10px}tr.row td:last-child{border-radius:0 10px 10px 0}.who{font-size:15px;font-weight:600}.bed,.muted{color:#7d8593;font-size:12px;margin-top:3px}.parts{display:flex;gap:24px;flex-wrap:wrap}.part .pl{color:#9aa3b2;font-size:12px;margin-bottom:6px}.dots{display:flex;gap:4px}.dot{width:18px;height:18px;border-radius:5px;background:#252b36;display:flex;align-items:center;justify-content:center;font-size:10px;color:#5d6675}.dot.on{background:#2f7d54;color:#c9f5dd}.dot.miss{background:#3a2126;color:#a45d6b}.bar{height:6px;border-radius:3px;background:#232833;overflow:hidden;margin-top:8px}.bar i{display:block;height:100%;background:linear-gradient(90deg,#3ddc84,#2f9e6b)}.pct{font-variant-numeric:tabular-nums;font-weight:600;font-size:15px;text-align:right}.pct small{display:block;color:#7d8593;font-weight:400;font-size:11px;margin-top:2px}.full{color:#3ddc84}.badge{display:inline-block;margin-left:5px;padding:1px 6px;border-radius:6px;background:#242a34;color:#9aa3b2;font-size:10px;font-weight:400;vertical-align:middle}.badge.dao{background:#27374a;color:#b9d9ff}.filters{display:grid;grid-template-columns:2fr repeat(4,1fr);gap:9px;margin:14px 0}.filters input,.filters select{width:100%;background:#15181f;border:1px solid #29303c;border-radius:8px;color:#e8eaed;padding:9px 10px;font-size:12px;outline:none}.filters input:focus,.filters select:focus{border-color:#527c69}.filters .wide{grid-column:span 2}.result-info{color:#8b93a1;font-size:12px;margin:10px 2px 14px}.npc{background:#15181f;border:1px solid #232833;border-radius:10px;margin:0 0 8px;overflow:hidden}.npc summary{cursor:pointer;padding:12px 14px;list-style:none;display:flex;align-items:center;gap:8px;flex-wrap:wrap}.npc summary::-webkit-details-marker{display:none}.npc summary:before{content:"›";color:#6f7787;font-size:20px;transform:rotate(0);transition:.15s}.npc[open] summary:before{transform:rotate(90deg)}.npc summary .location{margin-left:auto;color:#8b93a1;font-size:12px}.slots{border-top:1px solid #232833;padding:4px 14px 12px}.slot{padding:11px 0;border-bottom:1px solid #20252e}.slot:last-child{border-bottom:0}.slot-head{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.talent-name{font-size:14px;font-weight:600}.lock{margin-left:auto;font-size:11px;color:#b98289}.lock.on{color:#6edda2}.effect{color:#b4bdca;font-size:12px;line-height:1.7;margin-top:6px}.condition{color:#7d8593;font-size:11px;line-height:1.7;margin-top:4px}.q1{color:#9fd6a9}.q2{color:#82baf5}.q3{color:#c7a1ef}.q4{color:#e8c76d}.q5{color:#e88b82}.empty{background:#171a21;border:1px dashed #303846;border-radius:10px;padding:28px;text-align:center;color:#8b93a1;font-size:13px}.warnings{margin:12px 0;color:#c9a976;font-size:12px;line-height:1.8}.tip{margin-top:24px;color:#6f7787;font-size:12px;line-height:1.9}@media(max-width:850px){.filters{grid-template-columns:repeat(2,1fr)}.filters .wide{grid-column:span 2}.parts{gap:12px}.npc summary .location{margin-left:0;width:100%}}@media(max-width:560px){body{padding:18px 10px 40px}.filters{grid-template-columns:1fr}.filters .wide{grid-column:span 1}td{padding:9px 6px}.dot{width:15px;height:15px}.cards{gap:8px}.card{min-width:130px}}
"""
CSS += r"""
.talent-group{background:#15181f;border:1px solid #293140;border-radius:12px;margin:0 0 14px;overflow:hidden}.talent-head{padding:17px 18px}.talent-title{font-size:19px;font-weight:650;margin-right:7px}.talent-effect{color:#e0e6ed;background:#1b2029;border-left:3px solid #d4b45f;border-radius:5px;font-size:14px;line-height:1.85;margin-top:12px;padding:10px 12px}.talent-extra{color:#8f99a8;font-size:12px;line-height:1.7;margin-top:7px}.owners{border-top:1px solid #252c37;padding:9px 12px 12px}.owners-label{color:#8b93a1;font-size:11px;margin:3px 3px 8px}.owner{background:#11151b;margin-bottom:7px}.owner:last-child{margin-bottom:0}.owner summary{padding:11px 12px}.owner .slots{background:#15181f}.slot.focus{background:#1b2923;border-left:3px solid #55c78b;padding-left:10px}.slot.focus .talent-name{color:#8ee6b3}mark{background:#66551e;color:#fff0ae;border-radius:3px;padding:0 2px}.result-hint{color:#778292;font-size:11px;margin:-6px 2px 13px}@media(max-width:560px){.talent-head{padding:14px 12px}.talent-title{font-size:17px}.owners{padding:8px}.owner summary .location{width:auto;margin-left:auto}.owner .badge.hide-mobile{display:none}}
"""
CSS += r"""
.search-panel{background:#171b23;border:1px solid #293140;border-radius:12px;padding:15px;margin:16px 0 12px}.search-fields{display:grid;grid-template-columns:1fr 1fr;gap:14px}.search-field>span,.filter-field>span,.advanced-grid label>span{display:block;color:#aeb8c7;font-size:12px;margin:0 0 7px}.search-field:first-child>span{color:#d9c785}.search-field input,.filter-field select,.advanced-grid select{width:100%;background:#10141a;border:1px solid #303949;border-radius:8px;color:#e8eaed;padding:11px 12px;font-size:13px;outline:none}.search-field input:focus,.filter-field select:focus,.advanced-grid select:focus{border-color:#698c78;box-shadow:0 0 0 2px #263b34}.search-field input::placeholder{color:#667182}.filter-bar{display:grid;grid-template-columns:minmax(150px,1fr) minmax(190px,1.35fr) auto;align-items:end;gap:12px;margin:0 2px 14px}.filter-actions{display:flex;gap:8px}.filter-button{background:#1b222c;border:1px solid #35404f;border-radius:8px;color:#c6cfda;padding:10px 14px;min-height:40px;cursor:pointer;white-space:nowrap;font-size:12px}.filter-button:hover{background:#25303d;border-color:#526175}.filter-button.primary{color:#e2d7ac;border-color:#655d3d}.filter-count{color:#e8c76d}.advanced-filters{background:#141820;border:1px solid #293140;border-radius:10px;margin:0 0 14px;padding:0 13px}.advanced-filters summary{cursor:pointer;list-style:none;color:#9da8b7;font-size:12px;padding:11px 1px}.advanced-filters summary::-webkit-details-marker{display:none}.advanced-filters summary:before{content:"›";display:inline-block;margin-right:7px;transition:.15s}.advanced-filters[open] summary:before{transform:rotate(90deg)}.advanced-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;border-top:1px solid #252c37;padding:13px 0 15px}.owner summary .location{line-height:1.6;text-align:right}.category-badge{color:#d8c78f}.search-note{color:#758092;font-size:11px;margin:10px 2px 0}@media(max-width:850px){.filter-bar{grid-template-columns:1fr 1fr}.filter-actions{grid-column:span 2}.advanced-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.owner summary .location{text-align:left}}@media(max-width:560px){.search-panel{padding:12px}.search-fields,.filter-bar,.advanced-grid{grid-template-columns:1fr}.filter-actions{grid-column:span 1}.filter-button{flex:1}.owner summary .location{width:100%;text-align:left}}
"""
CSS += r"""
.item-group{background:#15181f;border:1px solid #293140;border-radius:12px;margin:0 0 14px;overflow:hidden}.item-tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:11px 12px 0}.sortbtn{background:#1b222c;border:1px solid #35404f;border-radius:7px;color:#9aa3b2;padding:5px 11px;font-size:11px;cursor:pointer}.sortbtn:hover{background:#25303d}.sortbtn.on{background:#263b34;border-color:#3d735b;color:#c9f5dd}.item-tools .meta{margin-left:auto;color:#778292;font-size:11px}.ratebar{width:62px;height:5px;border-radius:3px;background:#232833;overflow:hidden;display:inline-block;vertical-align:middle;margin-left:6px}.ratebar i{display:block;height:100%;background:#4fbf83}.badge.deadly{background:#3a2126;color:#e88b82}.loadmore{display:block;width:calc(100% - 24px);margin:8px 12px 12px;background:#1b222c;border:1px dashed #35404f;border-radius:8px;color:#9aa3b2;padding:9px;font-size:12px;cursor:pointer}.loadmore:hover{background:#25303d;color:#c6cfda}.steal-detail{flex-basis:100%;color:#8b93a1;font-size:11px;line-height:1.7;margin-top:2px}.steal-detail b{color:#b4bdca;font-weight:600}.steal-detail .bad{color:#e88b82}.npc-card .slots{padding:0 14px 12px}.item-group>summary{list-style:none;cursor:pointer}.item-group>summary::-webkit-details-marker{display:none}.item-arrow{color:#6f7787;font-size:17px;transition:.15s;display:inline-block}.item-group[open] .item-arrow{transform:rotate(90deg)}.item-head{padding:16px 18px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}.item-title{font-size:19px;font-weight:650}.item-stat{margin-left:auto;color:#8b93a1;font-size:12px}.owner .badge.steal{background:#22392e;color:#8ee6b3}.owner .badge.nosteal{background:#2a2d33;color:#8b93a1}.steal-ok{color:#6edda2;font-size:12px;font-weight:600}.steal-risk{color:#e88b82}.filter-bar.four{grid-template-columns:minmax(140px,1fr) minmax(165px,1.3fr) minmax(125px,1fr) auto}@media(max-width:850px){.filter-bar.four{grid-template-columns:1fr 1fr}.filter-bar.four .filter-actions{grid-column:span 2}}@media(max-width:560px){.filter-bar.four{grid-template-columns:1fr}.filter-bar.four .filter-actions{grid-column:span 1}.item-head{padding:13px 12px}.item-title{font-size:17px}.item-stat{margin-left:0;width:100%}}
"""

HTML_TEMPLATE = r"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>不问凡尘 · 仙友助手</title><style>__CSS__</style></head><body><div class="wrap"><h1>不问凡尘 · 仙友助手</h1><div class="sub">只读分析解密副本，不修改游戏存档；筛选条件会保留在本机浏览器。</div><div id="warnings" class="warnings"></div><div id="tabs" class="tabs"></div><section id="bedroom" class="panel"></section><section id="talent" class="panel"></section><section id="items" class="panel"></section><div class="tip">游戏保存后按 F8 可立即导出副本，平时插件每 60 秒自动同步。本页仅在数据变化时自动刷新。<br>配置来源优先使用游戏当前 YooAsset 清单；更新失败时使用兼容缓存或内置快照。若存档结构、加密或 Unity 格式大改，仍需更新工具。</div></div><script src="仙友助手版本.js"></script><script>
const INITIAL_VERSION=window.PROGRESS_VERSION||'';const DATA=__DATA__;
const $=id=>document.getElementById(id);const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const store={get(k,d){try{const v=localStorage.getItem(k);return v===null?d:JSON.parse(v)}catch(e){return d}},set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}};
const labels={bedroom:'十八摸',talent:'NPC天赋',items:'NPC物品'};let active=store.get('worldapart.active.tab.v2',DATA.enabled[0]||'');if(!DATA.enabled.includes(active))active=DATA.enabled[0]||'';
function sourceHtml(m){return `<div class="source">存档：${esc(m.src||'暂无')} ｜ 原始更新：${esc(m.stamp_text)} ｜ 配置：${esc(m.config)}${m.config_warning?' ｜ '+esc(m.config_warning):''}</div>`}
function showTab(name){active=name;store.set('worldapart.active.tab.v2',name);document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('active',x.id===name));document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x.dataset.tab===name))}
function initTabs(){$('tabs').innerHTML=DATA.enabled.map(n=>`<button class="tab" data-tab="${n}">${labels[n]}</button>`).join('');document.querySelectorAll('.tab').forEach(x=>x.onclick=()=>showTab(x.dataset.tab));if(!DATA.enabled.length){$('warnings').innerHTML=DATA.warnings.map(esc).join('<br>');return}showTab(active)}
function renderBedroom(){const m=DATA.modules.bedroom;if(!m)return;const rows=m.rows||[],done=rows.filter(r=>r.total>=18).length;const goals=[[1,'十八摸Ⅰ'],[3,'十八摸Ⅱ'],[5,'十八摸Ⅲ'],[10,'十八摸Ⅳ']];let cards=`<div class="card"><div class="k">已完成 18/18</div><div class="v">${done} <span>位</span></div></div>`;for(const [n,name] of goals)cards+=`<div class="card"><div class="k">${name}</div><div class="v">${done>=n?'已达成':'还差 '+(n-done)+' 位'}</div></div>`;const body=rows.map(r=>{const parts=r.parts.map(p=>`<div class="part"><div class="pl">${esc(p.label)}</div><div class="dots">${Array.from({length:6},(_,i)=>`<i class="dot ${p.got.includes(i)?'on':'miss'}">${i}</i>`).join('')}</div></div>`).join('');const pct=Math.min(100,Math.floor(r.total*100/18));return `<tr class="row"><td><div class="who">${esc(r.who)}${r.resident?'':'<span class="badge">未入住</span>'}</div><div class="bed">${esc(r.bed)}</div></td><td><div class="parts">${parts}</div></td><td style="width:150px"><div class="pct ${r.total>=18?'full':''}">${r.total}/18<small>${r.total>=18?'已完成':'进行中'}</small></div><div class="bar"><i style="width:${pct}%"></i></div></td></tr>`}).join('');$('bedroom').innerHTML=sourceHtml(m)+`<div class="cards">${cards}</div>${rows.length?`<table><thead><tr><th>仙友 / 寝室</th><th>各部位 6 段</th><th></th></tr></thead><tbody>${body}</tbody></table>`:'<div class="empty">暂无十八摸数据</div>'}<div class="tip">每个部位 6 段：0~3 为四段升阶，4 为循环段，5 为回落段。18/18 才算 1 位。</div>`}
const FILTER_KEY='worldapart.talent.filters.v3';
const FILTER_DEFAULTS={q:'',npc:'',region:'',location:'',category:'',quality:'',realm:'',unlocked:'',dao:''};
let filters=Object.assign({},FILTER_DEFAULTS,store.get('worldapart.talent.filters.v2',{}),store.get(FILTER_KEY,{}));
function uniq(values){return [...new Set(values)].sort((a,b)=>{const an=Number(a),bn=Number(b);if(a!==''&&b!==''&&!Number.isNaN(an)&&!Number.isNaN(bn))return an-bn;return String(a).localeCompare(String(b),'zh-CN')})}
function catValue(t){return t.category===null||t.category===undefined||t.category===''?'':String(t.category)}
function categoryLabel(t){const value=catValue(t),name=t.category_name||'';return value?(name?`${name}（${value}）`:`分类 ${value}`):'未分类'}
function initTalent(){
 const m=DATA.modules.talent;if(!m)return;
 const talents=m.talents||[],regions=uniq(m.rows.map(r=>r.region||r.location||'未知区域'));
 const categories=uniq(talents.map(catValue)),qualities=uniq(talents.map(t=>t.quality==null?'':String(t.quality))),realms=uniq(talents.map(t=>String(t.realm_id??0)));
 const opts=(values,kind)=>`<option value="">全部${kind}</option>`+values.map(v=>{
  let label=v,value=v;
  if(kind==='分类'){const sample=talents.find(t=>catValue(t)===v)||{category:v};label=v?categoryLabel(sample):'未分类';value=v||'__uncategorized__'}
  if(kind==='品质'){label=v?`品质 ${v}`:'未知品质';value=v||'__unknown__'}
  if(kind==='境界')label=(m.realms||{})[v]||`境界 ${v}`;
  return `<option value="${esc(value)}">${esc(label)}</option>`
 }).join('');
 const advancedKeys=['category','quality','realm','unlocked','dao'];
 const advancedCount=advancedKeys.filter(key=>filters[key]!=='').length;
 $('talent').innerHTML=sourceHtml(m)+`
  <div class="search-panel"><div class="search-fields">
   <label class="search-field"><span>找天赋</span><input id="fq" placeholder="输入天赋名称、效果、悬停或触发描述" value="${esc(filters.q)}"></label>
   <label class="search-field"><span>找 NPC（可选）</span><input id="fnpc" placeholder="输入 NPC 名称，与天赋条件叠加" value="${esc(filters.npc)}"></label>
  </div></div>
  <div class="filter-bar">
   <label class="filter-field"><span>区域</span><select id="fregion">${opts(regions,'区域')}</select></label>
   <label class="filter-field"><span>具体位置</span><select id="flocation"></select></label>
   <div class="filter-actions"><button type="button" id="fclear" class="filter-button">清空筛选</button></div>
  </div>
  <details id="fadvanced" class="advanced-filters"${advancedCount?' open':''}><summary>更多筛选 <span id="fadvancedcount" class="filter-count">${advancedCount?`（${advancedCount}）`:''}</span></summary><div class="advanced-grid">
   <label><span>天赋分类</span><select id="fcategory">${opts(categories,'分类')}</select></label>
   <label><span>天赋品质</span><select id="fquality">${opts(qualities,'品质')}</select></label>
   <label><span>天赋境界</span><select id="frealm">${opts(realms,'境界')}</select></label>
   <label><span>解锁状态</span><select id="funlocked"><option value="">全部解锁状态</option><option value="1">已解锁</option><option value="0">未解锁</option></select></label>
   <label><span>同道状态</span><select id="fdao"><option value="">全部同道状态</option><option value="1">已同道</option><option value="0">未同道</option></select></label>
  </div></details>
  <div id="tresult" class="result-info"></div><div id="tlist"></div>`;
 function updateLocations(){
  const locations=uniq(m.rows.filter(r=>!filters.region||(r.region||r.location||'未知区域')===filters.region).map(r=>r.location||'未知地点'));
  if(filters.location&&!locations.includes(filters.location))filters.location='';
  $('flocation').innerHTML=opts(locations,'具体位置');$('flocation').value=filters.location||'';
 }
 function updateAdvancedCount(){const count=advancedKeys.filter(key=>filters[key]!=='').length;$('fadvancedcount').textContent=count?`（${count}）`:''}
 function saveAndRender(){store.set(FILTER_KEY,filters);updateAdvancedCount();renderTalentList()}
 $('fregion').value=filters.region||'';
 updateLocations();
 for(const key of ['q','npc','location','category','quality','realm','unlocked','dao']){
  const node=$('f'+key);node.value=filters[key]??'';
  node.addEventListener(node.tagName==='INPUT'?'input':'change',()=>{filters[key]=node.value;saveAndRender()})
 }
 $('fregion').addEventListener('change',()=>{filters.region=$('fregion').value;updateLocations();saveAndRender()});
 $('fclear').addEventListener('click',()=>{filters=Object.assign({},FILTER_DEFAULTS);store.set(FILTER_KEY,filters);initTalent()});
 renderTalentList();
}
function hi(value,q){
 const text=String(value??'');if(!q)return esc(text);const lower=text.toLowerCase();let at=0,out='',found;
 while((found=lower.indexOf(q,at))>=0){out+=esc(text.slice(at,found))+'<mark>'+esc(text.slice(found,found+q.length))+'</mark>';at=found+q.length}
 return out+esc(text.slice(at));
}
function talentText(t){return [t.name,t.effect,t.hover,t.trigger].map(v=>String(v||'')).join('\n').toLowerCase()}
function talentBadges(t,m){const quality=t.quality==null?'未知品质':`品质 ${t.quality}`,cat=categoryLabel(t),realm=(m.realms||{})[String(t.realm_id??0)]||`境界 ${t.realm_id??0}`;return `<span class="badge">${esc(quality)}</span><span class="badge category-badge">${esc(cat)}</span><span class="badge">${esc(realm)}</span>`}
function talentMatchesFilters(t,s){
 if(filters.category==='__uncategorized__'&&catValue(t)!=='')return false;
 if(filters.category&&filters.category!=='__uncategorized__'&&catValue(t)!==filters.category)return false;
 if(filters.quality==='__unknown__'&&t.quality!=null)return false;
 if(filters.quality&&filters.quality!=='__unknown__'&&String(t.quality??'')!==filters.quality)return false;
 if(filters.realm!==''&&String(t.realm_id??0)!==filters.realm)return false;
 return filters.unlocked===''||String(s.unlocked?1:0)===filters.unlocked;
}
function talentSlotHtml(s,t,m,focus,q){
 const name=t.name||`天赋 #${s.talent_id}`;
 const req=s.required_realm?`<div class="condition">槽位要求：${esc((m.realms||{})[String(s.required_realm)]||('境界 '+s.required_realm))}</div>`:'';
 const conditions=(s.conditions||[]).length?`<div class="condition">解锁条件：${s.conditions.map(esc).join('；')}</div>`:'';
 return `<div class="slot${focus?' focus':''}"><div class="slot-head"><span class="muted">槽位 ${esc(s.slot_id??'?')}</span><span class="talent-name q${esc(t.quality??0)}">${hi(name,q)}</span>${talentBadges(t,m)}<span class="lock ${s.unlocked?'on':''}">${s.unlocked?'已解锁':'未解锁'}</span></div><div class="effect">${hi(t.effect||'暂无效果说明',q)}</div>${req}${conditions}</div>`;
}
function renderTalentList(){
 const m=DATA.modules.talent,talentMap=Object.fromEntries((m.talents||[]).map(t=>[String(t.id),t]));
 const q=filters.q.trim().toLowerCase(),npcQ=filters.npc.trim().toLowerCase();
 const groups={},npcSet=new Set();let slotCount=0;
 for(const row of m.rows){
  if(filters.region&&(row.region||row.location||'未知区域')!==filters.region)continue;
  if(filters.location&&(row.location||'未知地点')!==filters.location)continue;
  if(filters.dao!==''&&String(row.dao?1:0)!==filters.dao)continue;
  const npcText=[row.who,row.title].map(v=>String(v||'')).join('\n').toLowerCase();
  if(npcQ&&!npcText.includes(npcQ))continue;
  for(const s of row.slots||[]){
   const t=talentMap[String(s.talent_id)]||{},name=t.name||`天赋 #${s.talent_id}`,text=talentText(t);
   if(q&&!text.includes(q))continue;
   if(!talentMatchesFilters(t,s))continue;
   const rank=!q?0:name.toLowerCase().includes(q)?0:String(t.effect||'').toLowerCase().includes(q)?1:text.includes(q)?2:3;
   const key=String(s.talent_id);
   if(!groups[key])groups[key]={t,name,owners:[],rank};
   else groups[key].rank=Math.min(groups[key].rank,rank);
   groups[key].owners.push({row,s});npcSet.add(row.uid);slotCount++;
  }
 }
 const sorted=Object.values(groups).sort((a,b)=>a.rank-b.rank||Number(b.t.quality||0)-Number(a.t.quality||0)||a.name.localeCompare(b.name,'zh-CN'));
 const cards=sorted.map(group=>{
  const t=group.t,extras=[];
  if(t.hover)extras.push(`<div class="talent-extra">${hi('悬停说明：'+t.hover,q)}</div>`);
  if(t.trigger)extras.push(`<div class="talent-extra">${hi('触发说明：'+t.trigger,q)}</div>`);
  const owners=group.owners.sort((a,b)=>Number(b.row.dao)-Number(a.row.dao)||a.row.who.localeCompare(b.row.who,'zh-CN')).map(({row,s})=>{
   const all=(row.slots||[]).map(slot=>talentSlotHtml(slot,talentMap[String(slot.talent_id)]||{},m,String(slot.talent_id)===String(s.talent_id),q)).join('');
   const location=row.location_path||row.location||'未知地点';
   return `<details class="npc owner"><summary><span class="who">${hi(row.who,npcQ)}</span>${row.dao?'<span class="badge dao">已同道</span>':'<span class="badge">未同道</span>'}<span class="badge hide-mobile">全部 ${row.slots.length} 项天赋</span><span class="badge">槽位 ${esc(s.slot_id??'?')}</span><span class="lock ${s.unlocked?'on':''}">${s.unlocked?'已解锁':'未解锁'}</span><span class="location">${esc(location)}</span></summary><div class="slots">${all}</div></details>`;
  }).join('');
  return `<article class="talent-group"><div class="talent-head"><span class="talent-title q${esc(t.quality??0)}">${hi(group.name,q)}</span>${talentBadges(t,m)}<div class="talent-effect">${hi(t.effect||'暂无效果说明',q)}</div>${extras.join('')}</div><div class="owners"><div class="owners-label">${group.owners.length} 位 NPC 拥有此天赋；点击 NPC 可展开其全部天赋，当前天赋已高亮</div>${owners}</div></article>`;
 });
 $('tresult').textContent=`筛选结果：${sorted.length} 项天赋，${npcSet.size} 位 NPC，${slotCount} 条槽位记录（共 ${m.rows.length} 位有天赋记录）`;
 $('tlist').innerHTML=cards.length?cards.join(''):'<div class="empty">没有符合组合筛选条件的天赋</div>';
}
const ITEM_KEY='worldapart.item.filters.v1';
const ITEM_DEFAULTS={q:'',npc:'',region:'',location:'',type:'',quality:'',steal:''};
let itemFilters=Object.assign({},ITEM_DEFAULTS,store.get(ITEM_KEY,{}));
let itemCache=null;
let itemRenderState={groups:{},q:'',npcQ:''};
let itemSort=store.get('worldapart.item.sort.v1','rate');
let itemPage={};
function itemRateOf(o){return o.v.ok&&o.t.steal?o.t.steal.rate:-1}
function itemSortOwners(owners){
 const list=owners.slice();
 list.sort((a,b)=>{
  const okDiff=Number(b.v.ok)-Number(a.v.ok);
  if(okDiff)return okDiff;
  if(itemSort==='count'&&b.count!==a.count)return b.count-a.count;
  const rateDiff=itemRateOf(b)-itemRateOf(a);
  if(itemSort!=='name'&&rateDiff)return rateDiff;
  if(itemSort==='rate'&&b.count!==a.count)return b.count-a.count;
  return String(a.row.who).localeCompare(String(b.row.who),'zh-CN');
 });
 return list;
}
function stealDetailHtml(rule){
 if(!rule)return '';
 const parts=['一次最多 <b>'+rule.count+'</b> 个','善恶值 <b>'+rule.alignment+'</b>','好感 <b>'+rule.intimacy+'</b>'];
 if(rule.kill)parts.push('<span class="bad">失手触发击杀</span>');
 return '<span class="steal-detail">'+parts.join(' · ')+'</span>';
}
function itemOwnersHtml(iid){
 const state=itemRenderState,group=state.groups[iid];
 if(!group)return '';
 const all=itemSortOwners(group.owners);
 const limit=30*(itemPage[iid]||1),shown=all.slice(0,limit),rest=all.length-shown.length;
 const owners=shown.map(o=>{
  const badge=o.v.ok?'<span class="badge steal">可偷</span>':'<span class="badge nosteal">'+esc(o.v.label)+'</span>';
  let rate='';
  if(o.v.ok&&o.t.steal){
   rate='<span class="steal-ok">'+o.t.steal.rate+'%<span class="ratebar"><i style="width:'+Math.max(0,Math.min(100,o.t.steal.rate))+'%"></i></span></span>';
   if(o.t.steal.kill)rate+='<span class="badge deadly">致命</span>';
  }
  return '<details class="npc owner" data-uid="'+esc(o.row.uid)+'" data-item="'+esc(iid)+'"><summary><span class="who">'+hi(o.row.who,state.npcQ)+'</span>'+(o.row.realm?'<span class="badge">'+esc(o.row.realm)+'</span>':'')+badge+'<span class="badge">×'+esc(o.count)+'</span>'+rate+'<span class="location">'+esc(o.row.location_path||o.row.location||'未知地点')+'</span>'+stealDetailHtml(o.v.ok?o.t.steal:null)+'</summary><div class="slots"></div></details>';
 }).join('');
 const blocked=all.filter(o=>!o.v.ok).length;
 const labels={rate:'按成功率从高到低',count:'按持有数量从多到少',name:'按 NPC 名称排序'};
 const tools='<div class="item-tools">'
  +['rate','count','name'].map(k=>'<button type="button" class="sortbtn'+(itemSort===k?' on':'')+'" data-sort="'+k+'">'+({rate:'成功率',count:'数量',name:'名称'})[k]+'</button>').join('')
  +'<span class="meta">'+esc(labels[itemSort]||labels.rate)+'</span></div>';
 const head='<div class="owners-label">'+group.stealable+' 位可偷'+(blocked?' · '+blocked+' 位不可偷':'')+'；点击 NPC 可在下方展开其全部持有物品</div>';
 const more=rest?'<button type="button" class="loadmore" data-more="'+esc(iid)+'">显示更多（还有 '+rest+' 位）</button>':'';
 return tools+head+owners+more;
}
function itemIndex(){
 const m=DATA.modules.items;
 if(!itemCache||itemCache.m!==m)itemCache={m:m,cat:Object.fromEntries((m.catalog||[]).map(t=>[String(t.id),t])),rows:new Map(m.rows.map(r=>[r.uid,r]))};
 return itemCache;
}
function itemVerdict(row,t){
 if(!row.can_steal)return{ok:false,label:'NPC 不可偷'};
 if(!t.steal)return{ok:false,label:'物品不可偷'};
 return{ok:true,label:'可偷'};
}
function itemRate(group){
 const rates=group.owners.filter(o=>o.v.ok&&o.t.steal).map(o=>o.t.steal.rate);
 return rates.length?rates.reduce((a,b)=>a+b,0)/rates.length:0;
}
function npcItemsHtml(uid,focus){
 const idx=itemIndex(),row=idx.rows.get(uid);
 if(!row)return '';
 const list=(row.items||[]).map(pair=>{
  const t=idx.cat[String(pair[0])]||{name:'物品 #'+pair[0],quality:0,type:''};
  return{o:t,t:t,count:pair[1]||1,v:itemVerdict(row,t)};
 });
 list.sort((a,b)=>Number(b.v.ok)-Number(a.v.ok)||String(a.t.name).localeCompare(String(b.t.name),'zh-CN'));
 return list.map(o=>{
  const rule=o.t.steal,verdict=o.v.ok?'<span class="steal-ok">可偷</span>':'<span class="muted">'+esc(o.v.label)+'</span>';
  const current=focus!==undefined&&focus!==null&&String(o.t.id)===String(focus);
  const effect=o.v.ok&&rule?'<div class="effect">成功率 '+rule.rate+'% · 一次最多 '+rule.count+' 个 · 善恶值 '+rule.alignment+' · 好感 '+rule.intimacy+(rule.kill?' · <span class="steal-risk">失手触发击杀</span>':'')+'</div>':'';
  return '<div class="slot'+(current?' focus':'')+'"><div class="slot-head"><span class="talent-name q'+esc(o.t.quality??0)+'">'+esc(o.t.name)+'</span>'+(current?'<span class="badge steal">当前物品</span>':'')+'<span class="badge">×'+esc(o.count)+'</span><span class="badge">'+esc(o.t.type||'未分类')+'</span>'+verdict+'</div>'+effect+'</div>';
 }).join('');
}
function renderItemList(){
 itemPage={};
 const m=DATA.modules.items,idx=itemIndex();
 const q=itemFilters.q.trim().toLowerCase(),npcQ=itemFilters.npc.trim().toLowerCase();
 const groups={},npcSet=new Set();let pairCount=0;
 for(const row of m.rows){
  if(itemFilters.region&&(row.region||'未知区域')!==itemFilters.region)continue;
  if(itemFilters.location&&(row.location||'未知地点')!==itemFilters.location)continue;
  if(npcQ&&!((row.who+' '+(row.realm||'')).toLowerCase().includes(npcQ)))continue;
  for(const pair of row.items||[]){
   const iid=String(pair[0]),t=idx.cat[iid];
   if(!t)continue;
   if(q&&!String(t.name).toLowerCase().includes(q))continue;
   if(itemFilters.type&&(t.type||'未分类')!==(itemFilters.type==='__none__'?'未分类':itemFilters.type))continue;
   if(itemFilters.quality==='__unknown__'&&t.quality!=null)continue;
   if(itemFilters.quality&&itemFilters.quality!=='__unknown__'&&String(t.quality??'')!==itemFilters.quality)continue;
   const v=itemVerdict(row,t);
   if(itemFilters.steal==='1'&&!v.ok)continue;
   if(itemFilters.steal==='0'&&v.ok)continue;
   if(!groups[iid])groups[iid]={t:t,owners:[],stealable:0,total:0};
   groups[iid].owners.push({row:row,t:t,count:pair[1]||1,v:v});
   groups[iid].total+=pair[1]||1;
   if(v.ok){groups[iid].stealable++;const rate=t.steal?t.steal.rate:0;if(rate>(groups[iid].bestRate||0))groups[iid].bestRate=rate;}
   npcSet.add(row.uid);pairCount++;
  }
 }
 const npcMode=!q&&!!npcQ;
 if(npcMode){
  const npcs={};
  for(const row of m.rows){
   if(itemFilters.region&&(row.region||'未知区域')!==itemFilters.region)continue;
   if(itemFilters.location&&(row.location||'未知地点')!==itemFilters.location)continue;
   if(!(row.who+' '+(row.realm||'')).toLowerCase().includes(npcQ))continue;
   for(const pair of row.items||[]){
    const iid=String(pair[0]),t=idx.cat[iid];
    if(!t)continue;
    if(itemFilters.type&&(t.type||'未分类')!==(itemFilters.type==='__none__'?'未分类':itemFilters.type))continue;
    if(itemFilters.quality==='__unknown__'&&t.quality!=null)continue;
    if(itemFilters.quality&&itemFilters.quality!=='__unknown__'&&String(t.quality??'')!==itemFilters.quality)continue;
    const v=itemVerdict(row,t);
    if(itemFilters.steal==='1'&&!v.ok)continue;
    if(itemFilters.steal==='0'&&v.ok)continue;
    if(!npcs[row.uid])npcs[row.uid]={row:row,items:0,stealable:0};
    npcs[row.uid].items++;
    if(v.ok)npcs[row.uid].stealable++;
   }
  }
  const list=Object.values(npcs).sort((a,b)=>b.stealable-a.stealable||b.items-a.items||String(a.row.who).localeCompare(String(b.row.who),'zh-CN'));
  const cards=list.map(g=>'<details class="item-group npc-card" data-uid="'+esc(g.row.uid)+'"><summary class="item-head"><span class="item-arrow">›</span><span class="item-title">'+hi(g.row.who,npcQ)+'</span>'+(g.row.realm?'<span class="badge">'+esc(g.row.realm)+'</span>':'')+'<span class="badge steal">可偷 '+g.stealable+' 件</span><span class="item-stat">共 '+g.items+' 件 · '+esc(g.row.location_path||g.row.location||'未知地点')+'</span></summary><div class="slots"></div></details>');
  itemRenderState={groups:{},q:q,npcQ:npcQ};
  $('iresult').textContent='筛选结果：'+list.length+' 位 NPC，'+list.reduce((sum,g)=>sum+g.items,0)+' 件物品（正在按 NPC 查看，清空 NPC 搜索即回到物品列表）';
  $('ilist').innerHTML=cards.length?cards.join(''):'<div class="empty">没有符合条件的 NPC</div>';
  return;
 }
 const sorted=Object.values(groups).sort((a,b)=>b.stealable-a.stealable||itemRate(b)-itemRate(a)||String(a.t.name).localeCompare(String(b.t.name),'zh-CN'));
 const cards=sorted.map(group=>{
  const stat='可偷 '+group.stealable+' 处'+(group.bestRate?' · 最高 '+group.bestRate+'%':'')+' · 共 '+group.total+' 个';
  return '<details class="item-group" data-item="'+esc(group.t.id)+'"><summary class="item-head"><span class="item-arrow">›</span><span class="item-title q'+esc(group.t.quality??0)+'">'+hi(group.t.name,q)+'</span><span class="badge">'+esc(group.t.type||'未分类')+'</span><span class="badge">品质 '+esc(group.t.quality??'未知')+'</span><span class="item-stat">'+stat+'</span></summary><div class="owners"></div></details>';
 });
 itemRenderState={groups:Object.fromEntries(sorted.map(g=>[String(g.t.id),g])),q:q,npcQ:npcQ};
 $('iresult').textContent='筛选结果：'+sorted.length+' 种物品，'+npcSet.size+' 位 NPC，'+pairCount+' 条持有记录（共 '+m.rows.length+' 位 NPC 持有物品）';
 $('ilist').innerHTML=cards.length?cards.join(''):'<div class="empty">没有符合条件的物品</div>';
}
function initItems(){
 const m=DATA.modules.items;if(!m)return;
 const catalog=m.catalog||[],regions=uniq(m.rows.map(r=>r.region||'未知区域'));
 const types=uniq(catalog.map(t=>t.type||'未分类'));
 const qualities=uniq(catalog.map(t=>t.quality==null?'':String(t.quality)));
 const opts=(values,kind)=>'<option value="">全部'+kind+'</option>'+values.map(v=>{
  let label=v,value=v;
  if(kind==='类型'){label=v||'未分类';value=v||'__none__'}
  if(kind==='品质'){label=v?'品质 '+v:'未知品质';value=v||'__unknown__'}
  return '<option value="'+esc(value)+'">'+esc(label)+'</option>'
 }).join('');
 $('items').innerHTML=sourceHtml(m)+`
  <div class="search-panel"><div class="search-fields">
   <label class="search-field"><span>找物品</span><input id="iq" placeholder="输入物品名称" value="${esc(itemFilters.q)}"></label>
   <label class="search-field"><span>找 NPC（可选）</span><input id="inpc" placeholder="输入 NPC 名称，与物品条件叠加" value="${esc(itemFilters.npc)}"></label>
  </div></div>
  <div class="filter-bar four">
   <label class="filter-field"><span>区域</span><select id="iregion">${opts(regions,'区域')}</select></label>
   <label class="filter-field"><span>具体位置</span><select id="ilocation"></select></label>
   <label class="filter-field"><span>偷窃</span><select id="isteal"><option value="">全部持有者</option><option value="1">只看可偷</option><option value="0">只看不可偷</option></select></label>
   <div class="filter-actions"><button type="button" id="iclear" class="filter-button">清空筛选</button></div>
  </div>
  <details id="iadvanced" class="advanced-filters"><summary>更多筛选 <span id="iadvancedcount" class="filter-count"></span></summary><div class="advanced-grid">
   <label><span>物品类型</span><select id="itype">${opts(types,'类型')}</select></label>
   <label><span>物品品质</span><select id="iquality">${opts(qualities,'品质')}</select></label>
  </div></details>
  <div id="iresult" class="result-info"></div><div id="ilist"></div>`;
 const advancedKeys=['type','quality'];
 function updateCount(){const count=advancedKeys.filter(key=>itemFilters[key]!=='').length;$('iadvancedcount').textContent=count?`（${count}）`:''}
 function updateItemLocations(){
  const locations=uniq(m.rows.filter(r=>!itemFilters.region||(r.region||'未知区域')===itemFilters.region).map(r=>r.location||'未知地点'));
  if(itemFilters.location&&!locations.includes(itemFilters.location))itemFilters.location='';
  $('ilocation').innerHTML=opts(locations,'具体位置');$('ilocation').value=itemFilters.location||'';
 }
 function saveAndRender(){store.set(ITEM_KEY,itemFilters);updateCount();renderItemList()}
 $('iregion').value=itemFilters.region||'';updateItemLocations();
 for(const key of ['q','npc','location','type','quality','steal']){
  const node=$('i'+key);node.value=itemFilters[key]??'';
  node.addEventListener(node.tagName==='INPUT'?'input':'change',()=>{itemFilters[key]=node.value;saveAndRender()});
 }
 $('iregion').addEventListener('change',()=>{itemFilters.region=$('iregion').value;updateItemLocations();saveAndRender()});
 $('iclear').addEventListener('click',()=>{itemFilters=Object.assign({},ITEM_DEFAULTS);store.set(ITEM_KEY,itemFilters);initItems()});
 updateCount();renderItemList();
}
document.addEventListener('toggle',event=>{
 const node=event.target;
 if(!node||!node.classList||!node.open||!node.closest('#items'))return;
 if(node.classList.contains('npc-card')){
  const slots=node.querySelector('.slots');
  if(slots&&!slots.dataset.filled){slots.dataset.filled='1';slots.innerHTML=npcItemsHtml(node.dataset.uid)}
  return;
 }
 if(node.classList.contains('item-group')){
  const owners=node.querySelector('.owners');
  if(owners&&!owners.dataset.filled){owners.dataset.filled='1';owners.innerHTML=itemOwnersHtml(node.dataset.item)}
  return;
 }
 if(node.classList.contains('owner')){
  const box=node.querySelector('.slots');
  if(!box||box.dataset.filled)return;
  box.dataset.filled='1';
  box.innerHTML=npcItemsHtml(node.dataset.uid,node.dataset.item);
 }
},true);
function refreshItemOwners(iid){
 const nodes=document.querySelectorAll('#items .item-group');
 for(const node of nodes){
  if(node.dataset.item!==String(iid))continue;
  const box=node.querySelector('.owners');
  if(!box)return;
  box.dataset.filled='1';
  box.innerHTML=itemOwnersHtml(String(iid));
  return;
 }
}
document.addEventListener('click',event=>{
 if(!event.target.closest('#items'))return;
 const more=event.target.closest('[data-more]');
 if(more){
  const iid=more.dataset.more;
  itemPage[iid]=(itemPage[iid]||1)+1;
  refreshItemOwners(iid);
  return;
 }
 const sort=event.target.closest('[data-sort]');
 if(sort){
  itemSort=sort.dataset.sort;
  store.set('worldapart.item.sort.v1',itemSort);
  document.querySelectorAll('#items .item-group[open]').forEach(node=>refreshItemOwners(node.dataset.item));
 }
});
$('warnings').innerHTML=(DATA.warnings||[]).map(esc).join('<br>');initTabs();renderBedroom();initTalent();initItems();
let polledVersion=INITIAL_VERSION;setInterval(()=>{const script=document.createElement('script');script.src='仙友助手版本.js?t='+Date.now();script.onload=()=>{const next=window.PROGRESS_VERSION||'';if(next&&next!==polledVersion){location.reload();return}polledVersion=next||polledVersion;script.remove()};script.onerror=()=>script.remove();document.head.appendChild(script)},3000);
</script></body></html>"""


def build_html(payload):
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    data = data.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return HTML_TEMPLATE.replace("__CSS__", CSS).replace("__DATA__", data)


def _atomic_text(path, text):
    tmp = path + ".%s.tmp" % os.getpid()
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def disk_version():
    try:
        with open(OUT_VERSION, encoding="utf-8") as f:
            match = re.search(r'PROGRESS_VERSION="([0-9a-f]{64})"', f.read())
            return match.group(1) if match else ""
    except Exception:
        return ""


def write_outputs(payload):
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    version = hashlib.sha256((canonical + "\0" + CSS + "\0" + HTML_TEMPLATE).encode("utf-8")).hexdigest()
    previous = disk_version()
    changed = version != previous or not os.path.exists(OUT_HTML)
    if changed:
        _atomic_text(OUT_HTML, build_html(payload))
        _atomic_text(OUT_VERSION, 'window.PROGRESS_VERSION="%s";\n' % version)
    return version, changed


def console_summary(payload):
    for name in payload.get("enabled", []):
        module = payload["modules"].get(name) or {}
        rows = module.get("rows") or []
        if name == "bedroom":
            print("十八摸：%d 位仙友，已满 18/18：%d 位" % (
                len(rows), sum(1 for r in rows if r["total"] >= 18)))
        elif name == "talent":
            print("NPC天赋：%d 位 NPC，%d 个槽位，已解锁 %d 个" % (
                len(rows), sum(len(r["slots"]) for r in rows),
                sum(1 for r in rows for s in r["slots"] if s["unlocked"])))
        else:
            catalog = {str(t["id"]): t for t in module.get("catalog") or []}
            pairs = sum(len(r["items"]) for r in rows)
            stealable = sum(1 for r in rows if r["can_steal"]
                            for item_id, _ in r["items"]
                            if (catalog.get(str(item_id)) or {}).get("steal"))
            print("NPC物品：%d 位 NPC，%d 条持有记录，可偷 %d 条" % (len(rows), pairs, stealable))
        print("  来源：%s ｜ %s" % (module.get("src") or "暂无", module.get("stamp_text") or "未知"))
    for warning in payload.get("warnings") or []:
        print("提示：%s" % warning)


def settings_menu():
    cfg = load_cfg()
    while True:
        print("\n功能设置（只读工具，不会修改游戏存档）")
        print("  1. 十八摸进度：%s" % ("开启" if cfg["modules"]["bedroom"] else "关闭"))
        print("  2. NPC天赋：%s" % ("开启" if cfg["modules"]["talent"] else "关闭"))
        print("  3. NPC物品：%s" % ("开启" if cfg["modules"]["items"] else "关闭"))
        print("  4. 重新设置解密存档目录")
        print("  0. 保存并退出")
        choice = input("请选择: ").strip()
        if choice in ("1", "2", "3"):
            name = {"1": "bedroom", "2": "talent", "3": "items"}[choice]
            cfg["modules"][name] = not cfg["modules"][name]
        elif choice == "4":
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
                    "enabled": [n for n in ("bedroom", "talent", "items") if cfg["modules"][n]],
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
