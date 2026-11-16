# -*- coding: utf-8 -*-
"""打包数据收集与模块契约校验。

TouchProgress.spec 与发布前检查共用同一份收集逻辑：
    python -m tools.packaging --check      # 契约 + 快照 + datas 预演，失败返回 1
    python -m tools.packaging --datas      # 只打印 datas 清单

新增模块只需在 app/modules/<key>/__init__.py 声明 SNAPSHOT / EXTRA_SNAPSHOTS，
本文件不需要改动。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _use_root(root):
    if root and root not in sys.path:
        sys.path.insert(0, root)


def collect_snapshot_datas(root=None):
    """按模块声明收集内置快照：返回 (datas, 阻断问题)。

    datas 的格式与 PyInstaller 的 datas 一致：[(文件名, '.')]。
    缺文件或文件名冲突都属于阻断问题，不允许静默漏包。
    """
    root = root or ROOT
    _use_root(root)
    from app.modules import all as all_modules

    datas, owners, problems = [], {}, []
    for key, spec in sorted(all_modules().items(), key=lambda item: (item[1].ORDER, item[0])):
        for name in spec.SNAPSHOTS:
            if name in owners:
                problems.append("快照文件名冲突：%s 同时被 %s 与 %s 声明" % (name, owners[name], key))
                continue
            owners[name] = key
            if not os.path.isfile(os.path.join(root, name)):
                problems.append(
                    "缺少快照 %s（模块 %s），请运行：\n"
                    "  python meta_update.py --export-snapshots <游戏目录> . --only %s"
                    % (name, key, key))
                continue
            datas.append((name, "."))
    return datas, problems


def check(root=None):
    """发布前严格检查：返回 (阻断问题, 提示)。"""
    root = root or ROOT
    _use_root(root)
    from app import modules as plugins

    datas, problems = collect_snapshot_datas(root)
    problems = list(plugins.errors()) + problems
    notes = list(plugins.warnings())
    if "UnityPy" in sys.modules:
        notes.append("打包期不应导入 UnityPy，请检查模块顶层 import")
    if not plugins.all():
        problems.append("没有发现任何功能模块，请确认 app/modules 目录完整")
    return datas, problems, notes


def main(argv):
    root = ROOT
    if "--root" in argv:
        root = argv[argv.index("--root") + 1]
    datas, problems, notes = check(root)
    if "--datas" in argv:
        print(json.dumps([name for name, _ in datas], ensure_ascii=False))
    for note in notes:
        print("提示：%s" % note)
    if problems:
        for problem in problems:
            print("错误：%s" % problem)
        print("检查未通过：%d 项阻断问题" % len(problems))
        return 1
    if "--check" in argv or "--datas" not in argv:
        from app import modules as plugins
        print("检查通过：%d 个模块，%d 个内置快照" % (len(plugins.all()), len(datas)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
