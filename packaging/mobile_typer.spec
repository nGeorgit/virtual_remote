# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.depend.analysis import PyiModuleGraph


block_cipher = None
project_root = Path(SPEC).resolve().parents[1]


# PyInstaller 4.7 can crash in PyiModuleGraph.metadata_required() while scanning
# distribution metadata via hook-packaging.py. This app does not use runtime
# package metadata, so short-circuit that scan at spec execution time.
PyiModuleGraph.metadata_required = lambda self: set()


analysis = Analysis(
    [str(project_root / "run_mobile_typer.py")],
    pathex=[str(project_root), str(project_root / "src")],
    binaries=[],
    datas=[
        (str(project_root / "icons"), "icons"),
        (str(project_root / "manual.pdf"), "."),
    ],
    hiddenimports=[
        "qrcode",
        "qrcode.image.pil",
        "tkinter",
        "tkinter.messagebox",
        "_tkinter",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pkg_resources", "setuptools", "importlib.metadata", "importlib_metadata"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(analysis.pure, analysis.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="mobile-typer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    version=str(project_root / "packaging" / "windows_version_info.txt"),
)
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=False,
    name="mobile-typer",
)
