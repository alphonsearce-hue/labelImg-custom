# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['labelImg.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\megag\\Documents\\labelImg-custom\\custom', 'custom'), ('C:\\Users\\megag\\Documents\\labelImg-custom\\data', 'data'), ('C:\\Users\\megag\\Documents\\labelImg-custom\\libs', 'libs'), ('C:\\Users\\megag\\Documents\\labelImg-custom\\resources', 'resources')],
    hiddenimports=['PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5.QtXml'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['cv2', 'numpy', 'matplotlib', 'pandas', 'scipy', 'PIL', 'tkinter', 'IPython', 'pytest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LabelImgCustom_v3.0.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\megag\\Documents\\labelImg-custom\\resources\\icons\\app.png'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LabelImgCustom_v3.0.0',
)
