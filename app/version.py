# -*- coding: utf-8 -*-
"""版本号唯一来源。

发布脚本从 ``VERSION`` 派生出：
    - 代码与页面页脚（app/common.APP_VERSION）
    - 分发包名 dist/仙友助手v<版本>.zip
    - 使用说明首行、工坊 vdf 标题与更新说明
其它位置不要再手抄版本号，统一由 tools/release.py 生成或校验。
"""

VERSION = "1.8.0"
