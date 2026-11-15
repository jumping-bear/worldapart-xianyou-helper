# -*- coding: utf-8 -*-
"""读取存档副本，汇总各模块扫描结果。"""
import os
import time

import meta_update

from . import common, registry


def _source_payload(path, stamp, original, rows, meta_info):
    return {
        "rows": rows, "src": os.path.basename(path) if path else "",
        "original": original, "stamp": stamp,
        "stamp_text": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stamp)) if stamp else "未知",
        "config": meta_info.get("label", "未知"),
        "config_warning": meta_info.get("warning", ""),
    }


def render(dec, cfg):
    specs = registry.active(cfg["modules"])
    payload = {"enabled": [spec.KEY for spec in specs], "modules": {}, "warnings": []}
    if not specs:
        payload["warnings"].append("查询模块都已关闭。请运行“功能设置.bat”重新开启。")
        return payload
    game_dir = meta_update.game_dir_from_config(cfg, dec)
    if game_dir and game_dir != cfg.get("game_dir"):
        cfg["game_dir"] = game_dir
        common.save_cfg(cfg)
    metadata, report = meta_update.load_metadata(
        game_dir, common.BUILTIN_DIR, tuple(spec.KEY for spec in specs))
    payload["warnings"].extend(report.get("warnings") or [])
    metas = {spec.KEY: spec.meta(metadata) for spec in specs}
    prepared = {spec.KEY: spec.prepare(game_dir) for spec in specs}
    files = common.save_files(dec)
    originals = common.original_save_index(common.find_save_root())
    timed = [(path,) + common.source_time(path, originals) for path in files]
    chosen, errors = {}, []

    for path, stamp, original in timed:
        try:
            with open(path, "rb") as f:
                obj = common.unpack(f.read())
            if not isinstance(obj, dict) or not isinstance(obj.get("npcs"), dict):
                raise ValueError("存档缺少 NPC 数据")
            for spec in specs:
                key = spec.KEY
                previous = chosen.get(key)
                if previous is not None and getattr(spec, "SELECT", "latest") == "latest" \
                        and stamp <= previous["stamp"]:
                    continue
                rows = spec.post(spec.scan(obj, metas[key], prepared[key]),
                                 prepared[key], original, path)
                item = _source_payload(path, stamp, original, rows, report["modules"][key])
                score = getattr(spec, "score", None)
                if previous is None or score is None or score(rows) > score(previous["rows"]):
                    chosen[key] = item
        except Exception as e:
            errors.append("%s：%s" % (os.path.basename(path), e))

    for spec in specs:
        key = spec.KEY
        item = chosen.get(key)
        if item is None:
            rows = spec.scan({}, metas[key], prepared[key])
            item = _source_payload("", 0, "", rows, report["modules"][key])
        payload["modules"][key] = spec.enrich(item, metas[key], prepared[key])
    if not files:
        payload["warnings"].append("还没有可用存档副本，请先启动游戏并等待插件导出。")
    elif errors:
        payload["warnings"].append("跳过 %d 份无法解析的副本。" % len(errors))
        payload["errors"] = errors[:5]
    if any(key not in chosen for key in (spec.KEY for spec in specs)):
        payload["warnings"].append("暂未找到有效存档，请确认插件已导出 gameworld 副本。")
    return payload
