# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Image Drawer — standalone Windows GUI application.

PyInstaller 6.x auto-detects PySide6 and collects its Qt plugins.
"""

a = Analysis(
    ['ui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # OpenCV
        'cv2',
        'cv2.cv2',
        # NumPy
        'numpy',
        'numpy._core',
        'numpy._core._methods',
        'numpy.lib.format',
        # pynput
        'pynput',
        'pynput.keyboard',
        'pynput.keyboard._win32',
        'pynput.mouse',
        'pynput.mouse._win32',
        'pynput._util',
        'pynput._util.win32',
        # pygetwindow
        'pygetwindow',
        'pyrect',
        # Project modules
        'image_processor',
        'window_finder',
        'mouse_controller',
        'main',
        'i18n',
        'ui_thread_worker',
        'canvas_selector',
        # PySide6
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ImageDrawer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
    uac_admin=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ImageDrawer',
)