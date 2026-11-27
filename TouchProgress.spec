# -*- mode: python ; coding: utf-8 -*-
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

# 快照清单由各模块的 SNAPSHOT / EXTRA_SNAPSHOTS 自动收集，
# 新增模块不需要改动本文件；缺文件或重名会在这里直接失败。
sys.path.insert(0, SPECPATH)
from tools.packaging import collect_snapshot_datas, collect_module_datas  # noqa: E402

datas, snapshot_problems = collect_snapshot_datas(SPECPATH)
module_datas, module_problems = collect_module_datas(SPECPATH)
problems = snapshot_problems + module_problems
if problems:
    raise SystemExit("打包前检查失败：\n" + "\n".join(problems))
datas += module_datas
if "UnityPy" in sys.modules:
    raise SystemExit("打包期不应导入 UnityPy，请检查模块顶层 import")

binaries = []
hiddenimports = []
# 插件式功能模块（app/modules/<key>）由运行期动态导入，需显式收集。
try:
    hiddenimports += collect_submodules('app.modules')
except Exception:
    pass
# 覆盖模式的 pywebview 后端由运行期按平台动态导入，静态分析收不到。
hiddenimports += ['app.overlay', 'webview.platforms.winforms', 'webview.platforms.edgechromium']
# 只读取 TextAsset；压缩、类型树和 UnityPy 原生模块需要随 EXE 一起收集。
for package in ('UnityPy', 'lz4', 'brotli', 'tpk_ar', 'pythonnet', 'clr_loader'):
    try:
        d, b, h = collect_all(package)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# fsspec 的默认 hook 会收集全部可选后端，继而打入大量无关依赖。
excludes = [
    name for name in collect_submodules('fsspec')
    if name.startswith('fsspec.implementations.')
    and name not in {'fsspec.implementations.local', 'fsspec.implementations.memory'}
]
excludes += ['UnityPy.cli', 'UnityPy.tools', 'UnityPy.export']
excludes += [
    'torch', 'torchvision', 'scipy', 'pandas', 'numba', 'duckdb', 'narwhals',
    'networkx', 'pyarrow', 'polars', 'dask', 'ibis', 'cv2', 'sentencepiece', 'av',
    'altair', 'panel', 'fsspec.gui', 'fsspec.parquet', 'fsspec.fuse', 'fsspec.conftest',
]
# 运行期只读 TextAsset / 头像 webp；numpy 仅被已排除的 UnityPy.export 引用。
# setuptools 系列只服务开发期构建，打包后不需要。
excludes += ['numpy', 'setuptools', 'pip', 'wheel']
# matplotlib/PySide6 是构建环境里的开发用库，程序不 import；
# 但 PyInstaller 的 matplotlib hook 会连带收集 Qt 后端，曾把 EXE 从 27.7MB
# 撑到 79.1MB（2026-11-27 v2.4.0 重打包事故）。显式排除，环境再脏也不受影响。
excludes += ['matplotlib', 'PySide6', 'shiboken6']
hiddenimports = [
    name for name in hiddenimports
    if not any(name == excluded or name.startswith(excluded + '.') for excluded in excludes)
]

a = Analysis(
    ['xianyou_assistant.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='仙友助手',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
