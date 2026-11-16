# -*- coding: utf-8 -*-
"""模块插件发现器：每个功能模块一个目录，新增模块不再改动其它共享文件。

目录约定（app/modules/<key>/）：
    __init__.py        必需。导出 KEY、LABEL；可选 ORDER、TABLES、SCHEMA、SELECT、SNAPSHOT、
                       EXTRA_SNAPSHOTS（{文件名: f(tables, inspection)}，与内置快照一起导出）。
    build.py           可选。build(tables) -> dict，把配置表压成模块快照。
    scan.py            可选。scan(obj, meta, state)、meta(metadata)、prepare(game_dir)、
                       post(rows, state, original, path)、score(rows)、enrich(module, meta, state)、
                       summary(module)、empty()、builtin_ok(data)。
    view.js            可选。window.PROGRESS_VIEWS[key]=function(DATA){...}，渲染与事件自包含。
    view.css           可选。只写本模块自己的选择器，避免与其它模块抢样式。
    <snapshot>.json    可选。内置快照，文件名由 __init__.py 的 SNAPSHOT 声明。

__init__.py 只需把实现按标准名导出，例如：

    KEY, LABEL = "memoria", "留影石"
    ORDER, TABLES, SCHEMA = 20, {"tbmemoriaentry"}, 1
    from .build import build
    from .scan import scan, meta

约束：
    * 模块之间禁止互相 import，也不直接改 registry/meta_update/output 的集中表；
    * 配置表解包、文本清洗等通用能力从 meta_update 导入；
    * 单个模块导入失败只影响自己，其余模块照常加载。
"""
import importlib
import os

_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
_LOADED = None
_ERRORS = []


def _default_scan(obj, meta, state=None):
    return []


def _default_post(rows, state, original, path):
    return rows


def _default_enrich(module, meta, state=None):
    return module


def _default_prepare(game_dir):
    return None


def _read_asset(directory, name):
    try:
        with open(os.path.join(directory, name), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


class Plugin(object):
    """把模块目录包装成与老扫描模块一致的调用面，供 registry / render / meta_update 使用。"""

    def __init__(self, key, package, directory):
        self.KEY = key
        self.LABEL = str(getattr(package, "LABEL", "") or key)
        self.ORDER = _order(getattr(package, "ORDER", 1000))
        self.TABLES = frozenset(_strings(getattr(package, "TABLES", ())))
        self.SCHEMA = _positive(getattr(package, "SCHEMA", 1), 1)
        self.SELECT = str(getattr(package, "SELECT", "") or "latest")
        self.SNAPSHOT = str(getattr(package, "SNAPSHOT", "") or "")
        self.DIRECTORY = directory
        self.HAS_BUILD = callable(getattr(package, "build", None))
        self.build = getattr(package, "build", None) if self.HAS_BUILD else None
        self.scan = _function(package, "scan", _default_scan)
        self.meta = _function(package, "meta", lambda metadata: metadata.get(self.KEY) or {})
        self.prepare = _function(package, "prepare", _default_prepare)
        self.post = _function(package, "post", _default_post)
        self.enrich = _function(package, "enrich", _default_enrich)
        self.summary = _function(package, "summary", lambda module: "")
        self.score = getattr(package, "score", None)
        if not callable(self.score):
            self.score = None
        self.empty = getattr(package, "empty", None)
        if not callable(self.empty):
            self.empty = None
        self.builtin_ok = getattr(package, "builtin_ok", None)
        if not callable(self.builtin_ok):
            self.builtin_ok = None
        self.VIEW_JS = _read_asset(directory, "view.js")
        self.VIEW_CSS = _read_asset(directory, "view.css")
        self.EXTRA_SNAPSHOTS = _callables(getattr(package, "EXTRA_SNAPSHOTS", None))


def _strings(value):
    if isinstance(value, str):
        return (value,)
    try:
        return tuple(str(item) for item in value)
    except TypeError:
        return ()


def _positive(value, default):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _order(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 1000


def _function(package, name, default):
    function = getattr(package, name, None)
    return function if callable(function) else default


def _callables(value):
    """EXTRA_SNAPSHOTS：{文件名: f(tables, inspection)}，忽略非函数项。"""
    if not isinstance(value, dict):
        return {}
    return {str(name): make for name, make in value.items() if callable(make)}


def _discover():
    global _LOADED
    loaded, errors = {}, []
    for name in sorted(os.listdir(_DIRECTORY)):
        directory = os.path.join(_DIRECTORY, name)
        if name.startswith((".", "_")) or not os.path.isdir(directory):
            continue
        if not os.path.isfile(os.path.join(directory, "__init__.py")):
            continue
        try:
            package = importlib.import_module("%s.%s" % (__name__, name))
        except Exception as e:
            errors.append("%s：%s" % (name, e))
            continue
        key = str(getattr(package, "KEY", "") or name).strip()
        if not key:
            errors.append("%s：缺少 KEY" % name)
            continue
        if key in loaded:
            errors.append("%s：KEY 重复（%s）" % (name, key))
            continue
        loaded[key] = Plugin(key, package, directory)
    _LOADED = loaded
    _ERRORS[:] = errors


def all():
    """已加载的插件模块 {key: Plugin}；按需发现，失败项记录在 errors()。"""
    if _LOADED is None:
        _discover()
    return _LOADED


def errors():
    if _LOADED is None:
        _discover()
    return list(_ERRORS)


def reload():
    """重新扫描模块目录（测试或热更新用）。"""
    global _LOADED
    _LOADED = None
    del _ERRORS[:]
    return all()
