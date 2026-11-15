# -*- coding: utf-8 -*-
"""模块注册表：固定展示顺序，模块之间互不调用。"""
from .scanners import bedroom, event, forge, items, pill, talent

MODULES = (bedroom, talent, items, pill, forge, event)
_BY_KEY = {module.KEY: module for module in MODULES}


def get(key):
    return _BY_KEY[key]


def active(flags):
    return [module for module in MODULES if flags.get(module.KEY)]


def describe(key, module_payload):
    return _BY_KEY[key].summary(module_payload)
