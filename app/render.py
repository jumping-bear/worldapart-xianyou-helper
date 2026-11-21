# -*- coding: utf-8 -*-
"""读取存档副本，汇总各模块扫描结果。"""
import os
import time

import meta_update

from . import common, i18n, registry


def _source_payload(path, stamp, original, rows, meta_info):
    return {
        "rows": rows, "src": os.path.basename(path) if path else "",
        "original": original, "stamp": stamp,
        "stamp_text": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stamp)) if stamp else "未知",
        "config": meta_info.get("label", "未知"),
        "config_warning": meta_info.get("warning", ""),
    }


def _quarantine(path):
    """解析失败的副本多是上次写入中断留下的残片：改名后插件下一轮会重新导出。
    已经改过一次失败的就不再重复，避免和插件来回导出同一个坏文件。"""
    bad = path + ".bad"
    if os.path.exists(bad):
        return
    try:
        os.replace(path, bad)
    except OSError:
        pass


def _read_save(path):
    """读取副本；插件刚写完或正在替换时可能拿到不完整内容，稍等重试一次。"""
    last = None
    for attempt in range(2):
        try:
            with open(path, "rb") as fh:
                obj = common.unpack(fh.read())
            if not isinstance(obj, dict) or not isinstance(obj.get("npcs"), dict):
                raise ValueError("存档缺少 NPC 数据")
            return obj
        except Exception as exc:
            last = exc
            if attempt == 0:
                time.sleep(0.25)
    raise last


# SELECT = "best" 的模块要扫全部槽位才能挑出进度最高的一份，但不能每次都解包十几份存档：
# 归档槽位基本不再变化，按「路径 + 修改时间 + 大小」记住扫描结果，只有文件真变了才重算。
# 只存在进程内存里，工具重启即清空，不会读到跨版本的旧结构。
_best_cache = {}


def _file_stamp(path):
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def _cached_best(key, path):
    entry = _best_cache.get(key, {}).get(path)
    if entry and entry[0] == _file_stamp(path):
        return entry[1]
    return None


def _remember_best(key, path, rows):
    _best_cache.setdefault(key, {})[path] = (_file_stamp(path), rows)


def render(dec, cfg):
    specs = registry.active(cfg["modules"])
    payload = {"enabled": [spec.KEY for spec in specs],
               "tabs": [{"key": spec.KEY, "label": getattr(spec, "LABEL", spec.KEY),
                         "label_en": getattr(spec, "LABEL_EN", None) or getattr(spec, "LABEL", spec.KEY)}
                        for spec in specs],
               "modules": {}, "warnings": []}
    # 插件发现工坊文件不完整时会保留旧版并写这个文件，页面顶部直接提示玩家处理。
    try:
        error_path = os.path.join(str(dec), "_update_error.txt")
        with open(error_path, encoding="utf-8-sig") as handle:
            message = handle.read().strip()
        if message:
            payload["update_error"] = message
    except (OSError, TypeError):
        pass
    # 旧插件先把新 DLL 落成 .pending，退出游戏后才替换；第一次启动仍是旧插件，
    # 页面据此提示“本次可以用，插件侧下次启动完全生效”，避免玩家误以为要重装/退订。
    root = os.path.dirname(str(dec))
    pending = os.path.join(root, "plugins", "SaveDecryptProbe", "SaveDecryptProbe.dll.pending")
    payload["restart_needed"] = os.path.isfile(pending)
    for problem in registry.problems():
        payload["warnings"].append("功能模块加载失败：%s" % problem)
    for note in registry.notes():
        payload["warnings"].append("模块契约提示：%s" % note)
    if not specs:
        payload["warnings"].append("查询模块都已关闭。请运行“功能设置.bat”重新开启。")
        return payload
    game_dir = meta_update.game_dir_from_config(cfg, dec)
    if game_dir and game_dir != cfg.get("game_dir"):
        cfg["game_dir"] = game_dir
        common.save_cfg(cfg)
    # 界面语言决定整站语言：配置表文本也取同一语言列，避免“界面英文 + 数据中文”的半中半英。
    # 选「自动」时仍以游戏内语言为准（读不到游戏设置再按系统语言兜底）。
    ui_lang = i18n.resolve(cfg, common.game_language())
    if ui_lang == "en":
        game_lang = "en-US"
    else:
        game_lang = common.game_language() or "zh-Hans"
        if not str(game_lang).lower().startswith("zh"):
            game_lang = "zh-Hans"
    metadata, report = meta_update.load_metadata(
        game_dir, common.BUILTIN_DIR, tuple(spec.KEY for spec in specs), language=game_lang)
    payload["warnings"].extend(report.get("warnings") or [])
    metas = {spec.KEY: spec.meta(metadata) for spec in specs}
    prepared = {spec.KEY: spec.prepare(game_dir) for spec in specs}
    files = common.save_files(dec)
    originals = common.original_save_index(common.find_save_root())
    all_timed = [(path,) + common.source_time(path, originals) for path in files]
    # “best”模块要在同一角色的全部槽位里挑进度最高的一份；
    # “merge”模块把这些槽位里曾经获得过的进度合并成一份。
    # 两者都要全量解包；跨时间线的槽位不能只挑最高进度，否则页面会一直停在旧存档。
    select_modes = {spec.KEY: getattr(spec, "SELECT", "latest") for spec in specs}
    if any(mode != "latest" for mode in select_modes.values()):
        timed = sorted(all_timed, key=lambda item: item[1], reverse=True)
    else:
        latest = {}
        for item in all_timed:
            role = os.path.basename(item[0]).split("_slots_", 1)[0]
            best = latest.get(role)
            if best is None or item[1] > best[1]:
                latest[role] = item
        timed = sorted(latest.values(), key=lambda item: item[1], reverse=True)
    save_file = (cfg.get("save_file") or "").strip()
    if save_file:
        # 固定角色存的是角色目录前缀（不同角色的副本名都叫 gameworld.msgpack），
        # 兼容旧配置里存的副本名或原始文件名。
        pinned = []
        for item in all_timed:
            copy = os.path.basename(item[0])
            original = os.path.basename(item[2] or "")
            role = copy.split("_slots_", 1)[0]
            if save_file in (copy, original, role):
                pinned.append(item)
        if pinned:
            timed = pinned
        else:
            payload["warnings"].append("配置的存档角色已不存在，本次临时跟随最近存档。")
    chosen, errors = {}, []
    best_keys = {key for key, mode in select_modes.items() if mode != "latest"}
    merge_keys = {key for key, mode in select_modes.items() if mode == "merge"}
    # 合并只针对一个角色：固定角色优先，否则跟随最新存档的角色，不能把别的角色算进来。
    merge_role = os.path.basename(timed[0][0]).split("_slots_", 1)[0] if (merge_keys and timed) else ""
    merge_items = [item for item in timed
                   if merge_role and os.path.basename(item[0]).split("_slots_", 1)[0] == merge_role]
    merge_items.sort(key=lambda item: item[1])

    for path, stamp, original in timed:
        obj = None
        try:
            for spec in specs:
                key = spec.KEY
                if key in merge_keys:
                    continue
                previous = chosen.get(key)
                if previous is not None and getattr(spec, "SELECT", "latest") == "latest" \
                        and stamp <= previous["stamp"]:
                    continue
                rows = _cached_best(key, path) if key in best_keys else None
                if rows is None:
                    if obj is None:
                        obj = _read_save(path)
                    rows = spec.post(spec.scan(obj, metas[key], prepared[key]),
                                     prepared[key], original, path)
                    if key in best_keys:
                        _remember_best(key, path, rows)
                item = _source_payload(path, stamp, original, rows, report["modules"][key])
                score = getattr(spec, "score", None)
                if previous is None or score is None or score(rows) > score(previous["rows"]):
                    chosen[key] = item
        except Exception as e:
            errors.append("%s：%s" % (os.path.basename(path), e))
            _quarantine(path)

    # 合并类模块：按时间从旧到新扫同一角色的所有槽位，由模块把“曾经获得过”的部分并起来。
    for spec in specs:
        key = spec.KEY
        if key not in merge_keys or not merge_items:
            continue
        try:
            collected = []
            for path, stamp, original in merge_items:
                rows = _cached_best(key, path)
                if rows is None:
                    rows = spec.post(spec.scan(_read_save(path), metas[key], prepared[key]),
                                     prepared[key], original, path)
                    _remember_best(key, path, rows)
                collected.append(rows)
            rows = spec.merge(collected) if spec.merge else collected[-1]
            latest = merge_items[-1]
            item = _source_payload(latest[0], latest[1], latest[2], rows,
                                   report["modules"][key])
            item["merged"] = len(collected)
            chosen[key] = item
        except Exception as e:
            errors.append("合并存档：%s" % e)

    for spec in specs:
        key = spec.KEY
        item = chosen.get(key)
        if item is None:
            rows = spec.scan({}, metas[key], prepared[key])
            item = _source_payload("", 0, "", rows, report["modules"][key])
        payload["modules"][key] = spec.enrich(item, metas[key], prepared[key])
    event_rows = ((payload["modules"].get("event") or {}).get("rows") or {})
    if isinstance(event_rows, dict) and event_rows.get("character"):
        payload["character"] = event_rows["character"]
    if not files:
        payload["warnings"].append("还没有可用存档副本，请先启动游戏并等待插件导出。")
    elif errors:
        payload["warnings"].append("跳过 %d 份无法解析的副本。" % len(errors))
        payload["errors"] = errors[:5]
    if any(key not in chosen for key in (spec.KEY for spec in specs)):
        payload["warnings"].append("暂未找到有效存档，请确认插件已导出 gameworld 副本。")
    return payload
