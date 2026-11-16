# -*- coding: utf-8 -*-
"""模块注册表：所有功能模块都是 app/modules/<key>/ 插件，按 ORDER 排序。

模块之间互不 import；新增模块只需新建目录，不改动本文件。
"""
from . import modules as plugins


def _ordered():
    return tuple(spec for _key, spec in sorted(
        plugins.all().items(), key=lambda item: (item[1].ORDER, item[0])))


MODULES = _ordered()
_BY_KEY = {module.KEY: module for module in MODULES}


def get(key):
    return _BY_KEY[key]


def active(flags):
    """模块默认开启；配置里显式关闭的才跳过。"""
    flags = flags or {}
    return [module for module in MODULES if flags.get(module.KEY, True)]


def describe(key, module_payload):
    module = _BY_KEY.get(key)
    return module.summary(module_payload) if module is not None else ""


def tabs():
    return [{"key": module.KEY, "label": getattr(module, "LABEL", module.KEY)}
            for module in MODULES]


def assets_css():
    return "\n".join(getattr(module, "VIEW_CSS", "") or "" for module in MODULES)


def assets_js():
    return "\n".join(getattr(module, "VIEW_JS", "") or "" for module in MODULES)


def problems():
    return plugins.errors()
