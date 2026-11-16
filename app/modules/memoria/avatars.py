# -*- coding: utf-8 -*-
"""留影石头像快照：导出全部有头像的 NPC（按图片去重）。

- 图片按 `portraitIcon` 文件名去重，NPC 与图片的对应关系单独存 `icons`；
- 运行时只给页面实际出现的角色挂头像，不会把 2MB 图片全塞进页面；
- 游戏更新后重新执行 `--export-snapshots` 即可，缺失头像自动退回首字。
"""
import base64
import io
import os

AVATAR_SIZE = 96
IMAGE_QUALITY = 80


def _rows(value):
    if isinstance(value, dict):
        if isinstance(value.get("rows"), list):
            return [row for row in value["rows"] if isinstance(row, dict)]
        return [row for row in value.values() if isinstance(row, dict)]
    return [row for row in (value or []) if isinstance(row, dict)]


def _int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _stem(path):
    return os.path.basename(str(path)).rsplit(".", 1)[0]


def _encode(image):
    from PIL import Image

    resample = getattr(Image, "LANCZOS", Image.BICUBIC)
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    image = image.convert("RGBA").crop((left, top, left + side, top + side))
    image = image.resize((AVATAR_SIZE, AVATAR_SIZE), resample)
    buffer = io.BytesIO()
    try:
        image.save(buffer, "WEBP", quality=IMAGE_QUALITY, method=6)
        mime = "image/webp"
    except Exception:
        buffer = io.BytesIO()
        image.save(buffer, "PNG", optimize=True)
        mime = "image/png"
    return "data:%s;base64,%s" % (
        mime, base64.b64encode(buffer.getvalue()).decode("ascii"))


def build_avatars(tables, inspection):
    """EXTRA_SNAPSHOTS 入口：`avatars` 按图片去重，`icons` 负责 NPC → 图片。"""
    empty = {"schema": 2, "size": AVATAR_SIZE, "avatars": {}, "icons": {},
             "missing_count": 0}
    try:
        import UnityPy
        from PIL import Image  # noqa: F401
    except Exception as exc:
        empty["error"] = "%s: %s" % (type(exc).__name__, exc)
        return empty

    manifest = (inspection or {}).get("manifest") or {}
    root = (inspection or {}).get("root") or ""
    if not manifest.get("AssetList") or not root:
        empty["error"] = "缺少 YooAsset 清单"
        return empty

    icons, wanted, missing = {}, {}, 0
    for row in _rows(tables.get("tbnpcbasecfg")):
        npc_id = _int(row.get("id")) if isinstance(row, dict) else None
        if not npc_id:
            continue
        icon = row.get("portraitIcon")
        if not icon:
            missing += 1
            continue
        icons[str(npc_id)] = str(icon)
        wanted[str(icon)] = True

    groups = {}
    seen = set()
    for asset in manifest["AssetList"]:
        path = str(asset.get("AssetPath") or "")
        if path not in wanted or path in seen:
            continue
        seen.add(path)
        bundle_id = _int(asset.get("BundleID"))
        if bundle_id is None:
            continue
        groups.setdefault(bundle_id, []).append(path)

    avatars = {}
    for bundle_id, items in sorted(groups.items()):
        bundle = manifest["BundleList"][bundle_id]
        bundle_path = os.path.join(root, str(bundle["FileHash"]) + ".bundle")
        try:
            with open(bundle_path, "rb") as handle:
                raw = handle.read()
            offset = raw.find(b"UnityFS")
            if offset < 0:
                raise ValueError("不是可识别的 bundle")
            env = UnityPy.load(raw[offset:])
        except Exception:
            continue

        names = {_stem(path) for path in items}
        found = {}
        for obj in env.objects:
            if obj.type.name not in ("Sprite", "Texture2D"):
                continue
            try:
                item = obj.read()
                name = str(item.m_Name)
            except Exception:
                continue
            if name not in names:
                continue
            # Sprite 优先于 Texture2D（前者已按图集坐标裁好）
            if name not in found or obj.type.name == "Sprite":
                found[name] = item
            if len(found) == len(names):
                break

        for path in items:
            if path in avatars:
                continue
            item = found.get(_stem(path))
            if item is None or not hasattr(item, "image"):
                continue
            try:
                avatars[path] = _encode(item.image)
            except Exception:
                continue

    return {
        "schema": 2,
        "size": AVATAR_SIZE,
        "avatars": avatars,
        "icons": icons,
        "missing_count": missing,
    }
