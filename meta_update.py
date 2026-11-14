# -*- coding: utf-8 -*-
"""从游戏当前 YooAsset 清单更新查询元数据；标准库优先，UnityPy 延迟导入。"""
import hashlib
import json
import os
import re
import sys
import time

SCHEMA = 2
CACHE_SCHEMA = 3
TABLES = {
    "tbnpcbasecfg", "tbnpcbedroom", "tbscenepresentationinteraction",
    "tbscenepresentationaction", "tbspace", "tbnpctalent", "tbcultivaterealm",
}
MODULE_TABLES = {
    "bedroom": {"tbnpcbasecfg", "tbnpcbedroom", "tbscenepresentationinteraction",
                "tbscenepresentationaction"},
    "talent": {"tbnpcbasecfg", "tbspace", "tbnpctalent", "tbcultivaterealm"},
}
SLOT_LABELS = {
    "Face": "脸", "Waist": "腰", "Foot": "足", "Leg": "腿", "Armpit": "腋下",
    "Fan": "团扇", "Feather": "灵羽", "Gourd": "灵泉葫芦", "Grass": "草叶",
    "Stick": "短杖", "Bamboo": "竹枝", "Hug": "相拥",
}
# 游戏分类图标资源使用 combat/artisan/travel/wealth/rapport/personality。
CATEGORY_NAMES = {
    "1": "战斗", "2": "技艺", "3": "游历",
    "4": "财富", "5": "交情", "6": "性格",
}


def cache_directory():
    root = os.environ.get("LOCALAPPDATA")
    if not root:
        root = os.path.expanduser("~")
    return os.path.join(root, "WorldApartTouchProgress")


def game_dir_from_config(cfg, decrypted_dir=""):
    game = (cfg or {}).get("game_dir") or ""
    if game and os.path.isfile(os.path.join(game, "WorldApart.exe")):
        return os.path.normpath(game)
    if decrypted_dir:
        parent = os.path.dirname(os.path.normpath(decrypted_dir))
        if os.path.basename(parent).lower() == "bepinex":
            candidate = os.path.dirname(parent)
            if os.path.isfile(os.path.join(candidate, "WorldApart.exe")):
                return candidate
    return ""


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def _atomic_json(path, data):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    tmp = os.path.join(directory, ".%s.%s.tmp" % (os.path.basename(path), os.getpid()))
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def _version_key(path, manifest):
    version = str(manifest.get("PackageVersion") or "")
    numbers = tuple(int(x) for x in re.findall(r"\d+", version))
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = 0
    return numbers, version, stamp


def inspect_game(game_dir):
    if not game_dir:
        raise ValueError("未记录游戏目录")
    root = os.path.join(game_dir, "WorldApart_Data", "StreamingAssets", "yoo", "DefaultPackage")
    candidates = []
    for name in os.listdir(root):
        if not (name.startswith("DefaultPackage_") and name.endswith(".json")):
            continue
        path = os.path.join(root, name)
        manifest = _read_json(path)
        if not isinstance(manifest, dict):
            continue
        if not isinstance(manifest.get("AssetList"), list) or not isinstance(manifest.get("BundleList"), list):
            continue
        candidates.append((path, manifest))
    if not candidates:
        raise ValueError("找不到有效的 DefaultPackage 配置清单")
    path, manifest = max(candidates, key=lambda x: _version_key(x[0], x[1]))
    bundle_ids = set()
    for asset in manifest["AssetList"]:
        if not isinstance(asset, dict):
            continue
        asset_path = str(asset.get("AssetPath") or "")
        table = os.path.basename(asset_path).split(".", 1)[0].lower()
        if table in TABLES and asset_path.lower().endswith(".json"):
            try:
                bundle_ids.add(int(asset["BundleID"]))
            except (KeyError, TypeError, ValueError):
                pass
    bundles = []
    for bundle_id in sorted(bundle_ids):
        try:
            bundle = manifest["BundleList"][bundle_id]
            file_hash = str(bundle["FileHash"])
            file_path = os.path.join(root, file_hash + ".bundle")
            item = {
                "id": bundle_id, "hash": file_hash,
                "size": int(bundle.get("FileSize") or 0),
                "crc": str(bundle.get("FileCRC") or ""),
            }
            if not os.path.isfile(file_path):
                raise FileNotFoundError("配置资源缺失：%s.bundle" % file_hash)
            actual_size = os.path.getsize(file_path)
            if item["size"] and actual_size != item["size"]:
                raise ValueError("配置资源大小与清单不符：%s.bundle" % file_hash)
            bundles.append(item)
        except (IndexError, KeyError, TypeError, ValueError) as e:
            raise ValueError("清单中的配置资源信息无效：%s" % e)
    if not bundles:
        raise ValueError("当前清单没有所需配置表")
    source = {
        "package_version": str(manifest.get("PackageVersion") or ""),
        "manifest": os.path.basename(path), "bundles": bundles,
    }
    fingerprint = hashlib.sha256(
        json.dumps(source, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {"root": root, "manifest": manifest, "source": source, "fingerprint": fingerprint}


def _extract_tables(inspection):
    import UnityPy  # 仅在配置指纹变化时导入

    manifest = inspection["manifest"]
    wanted_bundles = {b["id"] for b in inspection["source"]["bundles"]}
    assets = {}
    for asset in manifest["AssetList"]:
        if not isinstance(asset, dict):
            continue
        path = str(asset.get("AssetPath") or "")
        name = os.path.basename(path).split(".", 1)[0].lower()
        if name in TABLES and path.lower().endswith(".json"):
            try:
                bid = int(asset["BundleID"])
            except (KeyError, TypeError, ValueError):
                continue
            if bid in wanted_bundles:
                assets[bid] = True
    tables = {}
    for bundle_id in sorted(assets):
        bundle = manifest["BundleList"][bundle_id]
        path = os.path.join(inspection["root"], str(bundle["FileHash"]) + ".bundle")
        with open(path, "rb") as f:
            data = f.read()
        offset = data.find(b"UnityFS")
        if offset < 0:
            raise ValueError("配置资源不是可识别的 Unity bundle：%s" % os.path.basename(path))
        env = UnityPy.load(data[offset:])
        for obj in env.objects:
            if obj.type.name != "TextAsset":
                continue
            item = obj.read()
            name = str(item.m_Name).lower()
            if name not in TABLES or name in tables:
                continue
            raw = item.m_Script
            if isinstance(raw, str):
                text = raw
            else:
                raw = bytes(raw)
                if not raw.lstrip()[:1] in (b"{", b"["):
                    continue
                text = raw.decode("utf-8-sig")
            if not text.lstrip()[:1] in ("{", "["):
                continue
            value = json.loads(text)
            if isinstance(value, (list, dict)):
                tables[name] = value
    return tables


def _rows(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return []


def _text(value):
    if isinstance(value, dict):
        for key in ("zh-Hans", "zh-Hant", "en-US"):
            if value.get(key):
                return str(value[key])
        return ""
    return "" if value is None else str(value)


def build_bedroom(tables):
    npcs = {r.get("id"): r for r in _rows(tables["tbnpcbasecfg"]) if isinstance(r, dict)}
    actions = {r.get("id"): r for r in _rows(tables["tbscenepresentationaction"]) if isinstance(r, dict)}
    interactions = {}
    for row in _rows(tables["tbscenepresentationinteraction"]):
        if isinstance(row, dict):
            interactions.setdefault(row.get("presentationId"), []).append(row)
    result = []
    for bed in _rows(tables["tbnpcbedroom"]):
        if not isinstance(bed, dict):
            continue
        npc_id = bed.get("npcId", bed.get("id"))
        actions_out = []
        seen_action_ids = set()
        rows = sorted(interactions.get(bed.get("presentationId"), []),
                      key=lambda r: (r.get("actionId") or 0, r.get("id") or 0))
        for interaction in rows:
            action_id = interaction.get("actionId")
            if action_id in seen_action_ids:
                continue
            seen_action_ids.add(action_id)
            action = actions.get(action_id) or {}
            slot = str(action.get("groupSlot") or "")
            actions_out.append({
                "id": action_id, "slot": slot,
                "label": SLOT_LABELS.get(slot) or slot or _text(interaction.get("label")) or str(action_id),
                "type": action.get("type"),
            })
        npc = npcs.get(npc_id) or {}
        result.append({
            "cfg": npc_id, "npcName": _text(npc.get("npcName")) or ("#%s" % npc_id),
            "bedroom": _text(bed.get("name")), "actions": actions_out,
        })
    if not result:
        raise ValueError("寝室配置为空")
    return result


def build_talent(tables):
    realms = {"0": "凡人"}
    for row in _rows(tables["tbcultivaterealm"]):
        if isinstance(row, dict) and row.get("id") is not None:
            realms[str(row["id"])] = _text(row.get("realm_name")) or ("境界 %s" % row["id"])
    spaces = {}
    for row in _rows(tables["tbspace"]):
        if isinstance(row, dict) and row.get("id") is not None:
            father = row.get("fatherSpace")
            if isinstance(father, dict):
                father = father.get("id")
            spaces[str(row["id"])] = {
                "name": _text(row.get("spaceName")) or ("地点 %s" % row["id"]),
                "realm_id": row.get("realm_id"),
                "father_id": "" if father in (None, "", 0, "0") else str(father),
            }

    def space_path(space_id):
        path, seen, current = [], set(), space_id
        while current in spaces and current not in seen:
            seen.add(current)
            path.append(current)
            current = spaces[current]["father_id"]
        path.reverse()
        names = []
        for item in path:
            name = spaces[item]["name"]
            if not names or names[-1] != name:
                names.append(name)
        return names

    for space_id, space in spaces.items():
        path = space_path(space_id) or [space["name"]]
        space["region"] = path[0]
        space["path"] = path
    npcs = {}
    for row in _rows(tables["tbnpcbasecfg"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        slots = []
        for slot in row.get("talent_slots") or []:
            if not isinstance(slot, dict):
                continue
            conditions = []
            for condition in slot.get("unlock_conditions") or []:
                if isinstance(condition, dict):
                    desc = _text(condition.get("desc"))
                    if desc:
                        conditions.append(desc)
            slots.append({
                "slot_id": slot.get("slot_id"),
                "required_npc_realm_id": slot.get("required_npc_realm_id", 0),
                "unlock_conditions": conditions,
            })
        npcs[str(row["id"])] = {
            "name": _text(row.get("npcName")) or _text(row.get("npcTitle")) or ("#%s" % row["id"]),
            "title": _text(row.get("npcTitle")),
            "can_be_dao_companion": bool(row.get("can_be_dao_companion")),
            "slots": slots,
        }
    talents = []
    for row in _rows(tables["tbnpctalent"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        talents.append({
            "id": row["id"], "name": _text(row.get("name")) or ("天赋 %s" % row["id"]),
            "quality": row.get("quality"), "effect": _text(row.get("effect_desc")),
            "category": row.get("category"),
            "category_name": CATEGORY_NAMES.get(str(row.get("category")), ""),
            "realm_id": row.get("realm_id", 0),
            "hover": _text(row.get("ui_hover_desc")),
            "trigger": _text(row.get("ui_trigger_desc")),
            "preview_only": bool(row.get("preview_only", False)),
        })
    if not talents:
        raise ValueError("NPC 天赋配置为空")
    return {"schema": SCHEMA, "talents": talents, "npcs": npcs, "spaces": spaces, "realms": realms}


def _builtin(directory, module):
    name = "bedroom_meta.json" if module == "bedroom" else "talent_meta.json"
    data = _read_json(os.path.join(directory, name))
    if module == "bedroom" and not isinstance(data, list):
        raise ValueError("十八摸内置快照无效")
    if module == "talent" and (not isinstance(data, dict) or not isinstance(data.get("talents"), list)):
        raise ValueError("天赋内置快照无效")
    return data


def load_metadata(game_dir, builtin_dir, modules=("bedroom", "talent"), cache_dir=None):
    """返回 (数据, 来源报告)；任何更新失败都回退，不阻断存档查询。"""
    modules = tuple(dict.fromkeys(modules))
    cache_dir = cache_dir or cache_directory()
    cache_path = os.path.join(cache_dir, "game_meta_cache.json")
    state_path = os.path.join(cache_dir, "meta_update_state.json")
    cache = _read_json(cache_path, {}) or {}
    if cache.get("schema") != CACHE_SCHEMA or not isinstance(cache.get("modules"), dict):
        cache = {"schema": CACHE_SCHEMA, "modules": {}}
    state = _read_json(state_path, {}) or {}
    result, report = {}, {"modules": {}, "warnings": [], "fingerprint": ""}
    inspection = None
    inspect_error = ""
    try:
        inspection = inspect_game(game_dir)
        report["fingerprint"] = inspection["fingerprint"]
        report["package_version"] = inspection["source"]["package_version"]
    except Exception as e:
        inspect_error = str(e)

    unresolved = []
    for module in modules:
        entry = (cache.get("modules") or {}).get(module) or {}
        data = entry.get("data")
        if inspection and data is not None and entry.get("fingerprint") == inspection["fingerprint"]:
            result[module] = data
            report["modules"][module] = {"source": "current", "label": "游戏当前配置"}
        else:
            unresolved.append(module)

    failed = state.get("fingerprint") == report["fingerprint"] and inspection
    failed_modules = set(state.get("modules") or []) if failed else set()
    to_extract = [m for m in unresolved if m not in failed_modules] if inspection else []
    errors = {}
    if to_extract:
        try:
            tables = _extract_tables(inspection)
            for module in to_extract:
                try:
                    missing = MODULE_TABLES[module] - set(tables)
                    if missing:
                        raise ValueError("缺少配置表：%s" % ", ".join(sorted(missing)))
                    data = build_bedroom(tables) if module == "bedroom" else build_talent(tables)
                    result[module] = data
                    cache["modules"][module] = {
                        "fingerprint": inspection["fingerprint"], "generated_at": int(time.time()), "data": data,
                    }
                    report["modules"][module] = {"source": "current", "label": "游戏当前配置"}
                except Exception as e:
                    errors[module] = str(e)
        except Exception as e:
            for module in to_extract:
                errors[module] = str(e)
        try:
            _atomic_json(cache_path, cache)
        except Exception as e:
            report["warnings"].append("配置已读取，但缓存写入失败：%s" % e)
        try:
            _atomic_json(state_path, {
                "fingerprint": inspection["fingerprint"], "modules": sorted(errors),
                "errors": errors, "time": int(time.time()),
            })
        except Exception:
            pass
    for module, message in (state.get("errors") or {}).items():
        if module in unresolved and module in failed_modules:
            errors[module] = str(message)

    for module in unresolved:
        if module in result:
            continue
        entry = (cache.get("modules") or {}).get(module) or {}
        if entry.get("data") is not None:
            result[module] = entry["data"]
            report["modules"][module] = {"source": "cache", "label": "兼容缓存"}
        else:
            try:
                result[module] = _builtin(builtin_dir, module)
                report["modules"][module] = {"source": "builtin", "label": "内置快照"}
            except Exception as e:
                errors[module] = str(e)
                result[module] = [] if module == "bedroom" else {
                    "schema": SCHEMA, "talents": [], "npcs": {}, "spaces": {}, "realms": {"0": "凡人"},
                }
                report["modules"][module] = {"source": "missing", "label": "无可用配置"}
        if module in errors:
            report["modules"][module]["warning"] = errors[module]
    if inspect_error and unresolved:
        report["warnings"].append("未读取游戏当前配置：%s" % inspect_error)
    for module, message in errors.items():
        if module in modules:
            report["warnings"].append("%s 配置更新失败，已使用兜底数据：%s" % (
                "十八摸" if module == "bedroom" else "NPC天赋", message))
    return result, report


def export_snapshots(game_dir, output_dir):
    inspection = inspect_game(game_dir)
    tables = _extract_tables(inspection)
    _atomic_json(os.path.join(output_dir, "bedroom_meta.json"), build_bedroom(tables))
    _atomic_json(os.path.join(output_dir, "talent_meta.json"), build_talent(tables))
    print("已导出当前配置快照：%s" % output_dir)


if __name__ == "__main__":
    if "--export-snapshots" in sys.argv:
        index = sys.argv.index("--export-snapshots")
        export_snapshots(sys.argv[index + 1], sys.argv[index + 2])
    else:
        cfg = _read_json(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), {}) or {}
        data, info = load_metadata(game_dir_from_config(cfg, cfg.get("decrypted_dir", "")),
                                   os.path.dirname(os.path.abspath(__file__)))
        print(json.dumps(info, ensure_ascii=False, indent=2))
