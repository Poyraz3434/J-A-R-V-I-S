# -*- mode: python ; coding: utf-8 -*-
"""JARVIS PyInstaller spec — tek codebase, platform için ayrı derleme.

Windows : pyinstaller jarvis.spec          (dist/JARVIS/JARVIS.exe)
macOS   : pyinstaller jarvis.spec          (dist/JARVIS.app veya JARVIS)

Notlar (bkz. BUILD.md):
* .env BUNDLE'LANMAZ → EXE'nin yanına elle konur (config.py frozen modda bakar).
* playwright hariç tutuldu (marketplace/web etkileşimi); kod ImportError ile
  zarif düşer. Eklemek istersen excludes listesinden çıkar + `playwright install`.
* data/curriculum.json datas ile gömülür (Özellik 8).
"""
import sys

block_cipher = None

# Dinamik (fonksiyon-içi) import'lara takviye — PyInstaller çoğu yakalar,
# yine de eksik kalan edge-case'ler için burada listelenir.
_HIDDEN = [
    "groq", "gtts", "speech_recognition", "playsound", "yfinance",
    "pytesseract", "PIL", "mss", "pygetwindow", "pyautogui",
    "bs4", "speedtest_cli", "pywhatkit", "numpy", "fitz",
    "requests", "urllib3",
    "selenium", "webdriver_manager",   # ATLAS web otomasyonu (fonksiyon-içi import)
    "services.ai_engine",
    "services.skill_registry", "services.task_center", "services.update_check",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("data/curriculum.json", "data"),   # Özellik 8: müfredat veri katmanı
    ],
    hiddenimports=_HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "playwright",          # 40MB+ driver; web etkileşimi opsiyonel (BUILD.md)
        "tkinter", "matplotlib", "IPython", "pytest",
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
    name="JARVIS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,            # windowed uygulama (konsolsuz)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="JARVIS.ico" if sys.platform == "win32" else None,  # generate_icon.py
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="JARVIS",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="JARVIS.app",
        icon="JARVIS.icns",       # generate_icon.py üretilir
        bundle_identifier="com.jarvis.app",
    )
