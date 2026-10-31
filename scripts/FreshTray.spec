# -*- mode: python ; coding: utf-8 -*-


from pathlib import Path
project_root = Path(SPECPATH).parent

a = Analysis(
    [str(project_root / 'src/main.pyw')],
    pathex=[],
    binaries=[],
    datas=[(str(project_root / 'src/assets'), 'assets'),
           (str(project_root / 'src/freshtray/qml'), 'freshtray/qml'),
           (str(project_root / 'docs/licenses'), 'notices/licenses'),
           (str(project_root / 'docs/THIRD_PARTY_NOTICES.md'), 'notices'),
           (str(project_root / 'LICENSE'), 'notices')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
              'PySide6.QtWebEngineQuick', 'PySide6.QtPdf', 'PySide6.QtPdfWidgets',
              'PySide6.Qt3DCore', 'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
              'PySide6.QtQuick3D', 'PySide6.QtCharts', 'PySide6.QtGraphs'],
    noarchive=False,
    optimize=0,
)
# Qt uses Windows' native ICU. A Poppler ICU with the same DLL name on PATH
# has version-suffixed exports and makes the frozen QtCore fail at startup.
# Keep this dependency on the OS, as in the source application.
a.binaries = [item for item in a.binaries
              if Path(item[0]).name.lower() not in ('icuuc.dll', 'icuin.dll', 'icu.dll')
              and not Path(item[0]).name.lower().startswith('icudt')]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FreshTray',
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
    icon=[str(project_root / 'src/assets/freshtray.ico')],
    version=str(project_root / 'scripts/version-info.txt'),
)
