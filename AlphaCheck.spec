# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


datas = collect_data_files("tkinterdnd2")
datas += [
    (str(path), "alphacheck/assets")
    for path in Path("src/alphacheck/assets").glob("*.png")
]

a = Analysis(
    ["main.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=["tkinterdnd2"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="EasyAlphaCheck",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="src/alphacheck/assets/easy_alpha_check.ico",
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
