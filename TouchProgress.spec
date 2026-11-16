# -*- mode: python ; coding: utf-8 -*-
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

# 快照清单由各模块的 SNAPSHOT / EXTRA_SNAPSHOTS 自动收集，
# 新增模块不需要改动本文件；缺文件或重名会在这里直接失败。
sys.path.insert(0, SPECPATH)
from tools.packaging import collect_snapshot_datas  # noqa: E402

datas, snapshot_problems = collect_snapshot_datas(SPECPATH)
if snapshot_problems:
    raise SystemExit("打包前检查失败：\n" + "\n".join(snapshot_problems))
if "UnityPy" in sys.modules:
    raise SystemExit("打包期不应导入 UnityPy，请检查模块顶层 import")

binaries = []
hiddenimports = []
# 插件式功能模块（app/modules/<key>）由运行期动态导入，需显式收集。
try:
    hiddenimports += collect_submodules('app.modules')
except Exception:
    pass
# 只读取 TextAsset；压缩、类型树和 UnityPy 原生模块需要随 EXE 一起收集。
for package in ('UnityPy', 'lz4', 'brotli', 'tpk_ar'):
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
