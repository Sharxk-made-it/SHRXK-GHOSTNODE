# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for GHOSTNODE  (PyInstaller >= 6)
#
# One-DIRECTORY build on purpose (not --onefile):
#   * onefile unpacks itself into %TEMP% on every launch = traces on the host PC
#   * onedir starts faster and triggers fewer antivirus false positives
# Result: dist/GHOSTNODE/GHOSTNODE.exe  (+ _internal/ with the runtime)

from pathlib import Path

ROOT = Path(SPECPATH)
ICON = ROOT / "assets" / "icons" / "ghostnode.ico"

# Qt modules GHOSTNODE does not use: excluded to keep the USB footprint small.
EXCLUDES = [
    "tkinter", "unittest", "pydoc", "test",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets",
    "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQml",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtPositioning", "PySide6.QtRemoteObjects",
]

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "assets"), "assets")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GHOSTNODE",
    debug=False,
    strip=False,
    upx=False,            # UPX raises antivirus false positives; not worth it
    console=False,        # windowed app, no console flash
    icon=str(ICON) if ICON.exists() else None,
    uac_admin=False,      # never ask for administrator rights
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="GHOSTNODE",
)
