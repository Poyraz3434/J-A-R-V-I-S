#!/usr/bin/env python3
"""JARVIS tek komutla sürüm derleme betiği.

Sürümün tek kaynağı ``config.APP_VERSION``'dur. Bu betik:
  1. ``installer.iss`` içindeki ``MyAppVersion`` değerini senkronlar,
  2. (isteğe bağlı) PyInstaller ile EXE'yi derler,
  3. Inno Setup (ISCC) ile Windows kurucusunu üretir.

Kullanım:
    python build_installer.py               # senkron + EXE + kurucu
    python build_installer.py --skip-exe    # senkron + kurucu (dist hazır ise)
    python build_installer.py --sync-only   # yalnızca sürüm senkronu

Not: macOS derlemesi (.app) ayrı olarak bir Mac'te ``pyinstaller jarvis.spec``
ile yapılır; bu betik yalnızca Windows kurucusunu üretir.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ISS_PATH = ROOT / "installer.iss"
_OUTPUT_DIR = ROOT / "Output"
_VERSION_DEFINE_RE = re.compile(r'(#define\s+MyAppVersion\s+")[^"]+(")')


def sync_installer_version(version: str) -> bool:
    """``installer.iss`` içindeki MyAppVersion değerini günceller.

    Args:
        version: Yazılacak sürüm (config.APP_VERSION).

    Returns:
        Değişiklik yapıldıysa True; zaten eşitse False.

    Raises:
        SystemExit: ``#define MyAppVersion`` satırı bulunamazsa.
    """
    text = ISS_PATH.read_text(encoding="utf-8")
    patched, count = _VERSION_DEFINE_RE.subn(rf"\g<1>{version}\g<2>", text, count=1)
    if count == 0:
        raise SystemExit(f"HATA: {ISS_PATH} içinde 'MyAppVersion' tanımı bulunamadı.")
    if patched == text:
        print(f"[Sync] MyAppVersion zaten {version} — değişiklik yok")
        return False
    ISS_PATH.write_text(patched, encoding="utf-8")
    print(f"[Sync] MyAppVersion → {version}")
    return True


def build_exe() -> None:
    """PyInstaller ile EXE'yi derler (jarvis.spec, onedir + windowed)."""
    print("[Build] PyInstaller EXE derlemesi başlıyor (~2 dk)...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "jarvis.spec", "--noconfirm"],
        cwd=ROOT,
    )
    if result.returncode != 0:
        raise SystemExit(f"HATA: PyInstaller başarısız (exit={result.returncode}).")


def find_iscc() -> Path:
    """Inno Setup 6 derleyicisini (ISCC.exe) bilinen konumlarda arar."""
    candidates = [
        Path.home() / "AppData" / "Local" / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit(
        "HATA: ISCC.exe (Inno Setup 6) bulunamadı. "
        "winget install --id JRSoftware.InnoSetup ile kurun."
    )


def build_installer(version: str) -> Path:
    """Inno Setup ile kurucuyu üretir ve çıktı yolunu döndürür."""
    iscc = find_iscc()
    print("[Build] Inno Setup kurucusu derlemesi başlıyor (~1 dk)...")
    result = subprocess.run([str(iscc), str(ISS_PATH)], cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"HATA: Inno Setup derlemesi başarısız (exit={result.returncode}).")
    output = _OUTPUT_DIR / f"JARVIS-Setup-{version}.exe"
    if not output.is_file():
        raise SystemExit(f"HATA: Beklenen kurucu üretilmedi: {output}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="config.APP_VERSION'dan sürüm senkronu + EXE + kurucu derlemesi."
    )
    parser.add_argument(
        "--skip-exe", action="store_true",
        help="PyInstaller adımını atla (dist hazır olduğunda kurucuyu hızlı yeniden üret).",
    )
    parser.add_argument(
        "--sync-only", action="store_true",
        help="Yalnızca installer.iss sürümünü senkronla, hiçbir şey derleme.",
    )
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    from config import APP_VERSION  # noqa: E402 — tek sürüm kaynağı

    sync_installer_version(APP_VERSION)
    if args.sync_only:
        print("[Sync] --sync-only: derleme adımları atlandı.")
        return 0
    if not args.skip_exe:
        build_exe()
    output = build_installer(APP_VERSION)
    size_mb = output.stat().st_size / (1024 * 1024)
    print("=" * 60)
    print(f"[OK] Kurucu hazır: {output}  ({size_mb:.1f} MB)")
    print(f"[OK] Sürüm: {APP_VERSION}  (tek kaynak: config.py)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
