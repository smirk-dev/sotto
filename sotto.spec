# PyInstaller spec for Sotto (onedir, windowed).
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for pkg in ("openvino", "openvino_genai", "openvino_tokenizers"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["huggingface_hub", "hf_xet"],
    hookspath=[],
    runtime_hooks=[],
    # openvino_telemetry: never bundled — ovc (unused converter tool) falls back
    # to its built-in stub, and the app makes no network calls at runtime.
    # evdev is the Linux-only hotkey backend (sotto.hotkey_linux); never bundled on Windows.
    excludes=["evdev", "openvino_telemetry", "tkinter", "test", "unittest",
              "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D",
              "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtWebEngineCore",
              "PySide6.QtWebEngineWidgets", "PySide6.QtMultimedia",
              "PySide6.QtCharts", "PySide6.QtDataVisualization"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Sotto",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="build_assets/sotto.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Sotto",
)
