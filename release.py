#!/usr/bin/env python3
"""JARVIS sürüm çıkarma otomasyonu.

Tek komutla güvenli sürüm çıkarma zinciri:
  1. Kapı: ruff lint + tam test paketi (offscreen Qt) — geçilmezse durur.
  2. ``config.py`` → ``APP_VERSION`` güncellemesi (tek sürüm kaynağı).
  3. ``installer.iss`` sürüm senkronu (``build_installer.sync_installer_version``).
  4. ``CHANGELOG.md`` yeni bölüm (kullanıcı notları + otomatik commit listesi).
  5. Git commit (BOM'suz UTF-8 dosyayla — Türkçe karakter güvenli).
  6. Dağıtım derlemesi: ``build_installer.py`` (``--skip-build`` ile atlanır).
  7. Git etiketi ``v<sürüm>`` — yalnızca tüm zincir başarılıysa atılır.

Kullanım:
    python release.py --bump patch                     # 10.0.0 → 10.0.1
    python release.py --bump minor --notes "..."      # 10.0.0 → 10.1.0
    python release.py --version 11.0.0                 # açık hedef sürüm
    python release.py --bump patch --skip-build        # commit + etiket, derleme yok
    python release.py --bump patch --dry-run           # yalnızca önizleme

Notlar:
- Kapı geçilmeden hiçbir dosya yazılmaz.
- Hedef sürüm mevcut sürüme eşitse veya ``v<sürüm>`` etiketi zaten varsa durur.
- Türkçe ``--notes`` için PowerShell'de kodlama riski varsa ``--notes-file`` kullanın.
- Dağıtım artifact'leri (dist/, Output/) gitignore'dur; derleme sonrası ağaç temiz kalır.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.py"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"
GIT_FALLBACK = Path(r"C:\Program Files\Git\cmd\git.exe")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
APP_VERSION_RE = re.compile(r'APP_VERSION\s*=\s*"([^"]+)"')


class ReleaseError(SystemExit):
    """Kullanıcı dostu sürüm hatası: mesaj yazdırılır, süreç 1 ile çıkar."""


def _git() -> str:
    """git çalıştırılabilirini bulur (PATH → bilinen kurulum yolu)."""
    found = shutil.which("git")
    if found:
        return found
    if GIT_FALLBACK.is_file():
        return str(GIT_FALLBACK)
    raise ReleaseError(f"HATA: git bulunamadı — PATH'te değil ve {GIT_FALLBACK} yok.")


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Alt komutu UTF-8/offscreen ortamıyla proje kökünde çalıştırır."""
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    kwargs.setdefault("cwd", ROOT)
    return subprocess.run(cmd, env=env, **kwargs)


def _run_git(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """git alt komutunu çalıştırır (çıktılar UTF-8 olarak çözülür)."""
    kwargs.setdefault("encoding", "utf-8")
    return _run([_git(), *args], **kwargs)


def _configure_stdio() -> None:
    """Windows konsolunda (cp1254) '→' gibi karakterlerin print patlamasını önler."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            pass


def read_current_version() -> str:
    """config.py içinden APP_VERSION değerini okur."""
    text = CONFIG_PATH.read_text(encoding="utf-8")
    m = APP_VERSION_RE.search(text)
    if not m:
        raise ReleaseError(f"HATA: {CONFIG_PATH} içinde APP_VERSION bulunamadı.")
    return m.group(1)


def compute_next_version(current: str, bump: str | None, explicit: str | None) -> str:
    """Hedef sürümü hesaplar; semver biçimini ve tekrarları doğrular."""
    if explicit is not None:
        target = explicit.strip().lstrip("v")
    else:
        major, minor, patch = (int(p) for p in current.split("."))
        if bump == "major":
            target = f"{major + 1}.0.0"
        elif bump == "minor":
            target = f"{major}.{minor + 1}.0"
        else:
            target = f"{major}.{minor}.{patch + 1}"
    if not SEMVER_RE.match(target):
        raise ReleaseError(f"HATA: '{target}' geçerli bir semver değil (ör. 10.2.0).")
    if target == current:
        raise ReleaseError(f"HATA: hedef sürüm mevcut sürüme eşit ({current}).")
    tags = _run_git(["tag", "--list", f"v{target}"], capture_output=True, text=True)
    if tags.stdout.strip():
        raise ReleaseError(f"HATA: v{target} etiketi zaten var.")
    return target


def run_gate() -> None:
    """Kapı: ruff lint + tam test paketi. Geçilmezse zinciri durdurur."""
    print("[1/7] Kapı: ruff lint ...")
    ruff = _run([sys.executable, "-m", "ruff", "check", "."],
                capture_output=True, text=True)
    if ruff.returncode != 0:
        print(ruff.stdout or ruff.stderr)
        raise ReleaseError("HATA: ruff kapısı geçilemedi — sürüm durduruldu.")
    print("      ruff: OK")
    print("[1/7] Kapı: test paketi (offscreen Qt) ...")
    tests = _run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                 capture_output=True, text=True)
    tail = "\n".join((tests.stderr or tests.stdout).strip().splitlines()[-3:])
    if tests.returncode != 0:
        print(tail)
        raise ReleaseError("HATA: test paketi başarısız — sürüm durduruldu.")
    print(f"      tests: OK\n      {tail.splitlines()[0] if tail else ''}")



def update_config_version(new: str) -> None:
    """config.py içindeki APP_VERSION değerini yeni sürümle değiştirir."""
    text = CONFIG_PATH.read_text(encoding="utf-8")
    new_text, n = APP_VERSION_RE.subn(f'APP_VERSION = "{new}"', text, count=1)
    if n != 1:
        raise ReleaseError("HATA: config.py içinde APP_VERSION değiştirilemedi.")
    CONFIG_PATH.write_text(new_text, encoding="utf-8", newline="\n")
    print(f"[2/7] config.py → APP_VERSION = {new}")


def _recent_commits(tag: str | None, limit: int = 30) -> list[str]:
    """Önceki etiketten (yoksa HEAD~limit) bu yana girilen commit özetleri."""
    args = ["log", "--oneline", "--no-decorate", f"-{limit}"]
    if tag:
        args.append(f"v{tag}..HEAD")
    res = _run_git(args, capture_output=True, text=True)
    return [l for l in res.stdout.strip().splitlines() if l.strip()]


def write_changelog(new: str, notes: str | None) -> None:
    """CHANGELOG.md başına yeni sürüm bölümü ekler (özet + commit listesi)."""
    today = _dt.date.today().isoformat()
    prev = _run_git(["describe", "--tags", "--abbrev=0"],
                    capture_output=True, text=True).stdout.strip() or None
    commits = _recent_commits(prev)
    lines = [
        f"## [{new}] — {today}",
        "",
        notes.strip() if notes else f"JARVIS v{new} bakım/maintenance sürümü.",
        "",
    ]
    if commits:
        lines += ["### Bu sürümde", ""]
        lines += [f"- {c}" for c in commits]
        lines.append("")
    body = "\n".join(lines)
    old = CHANGELOG_PATH.read_text(encoding="utf-8")
    head, sep, rest = old.partition("\n\n## [")
    if sep:  # mevcut bölümlerin önüne ekle
        rest = "## [" + rest
    else:  # henüz bölüm yoksa: dosyanın sonuna ekle
        head, rest = old.rstrip("\n") + "\n", ""
    CHANGELOG_PATH.write_text(head.rstrip("\n") + "\n\n" + body + "\n" + rest,
                              encoding="utf-8", newline="\n")
    print(f"[3/7] CHANGELOG.md → [{new}] bölümü ({len(commits)} commit)")


def _git_commit_version(new: str) -> None:
    """Sürüm dosyalarını sahneye alır ve UTF-8 mesaj dosyasıyla commit eder."""
    _run_git(["add", str(CONFIG_PATH), str(CHANGELOG_PATH)])
    msg = (f"release: v{new}\n\n"
           f"- config.py APP_VERSION → {new}\n"
           f"- installer.iss sürüm senkronu (build_installer)\n"
           f"- CHANGELOG.md yeni bölüm\n")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n",
                                      delete=False, suffix=".txt") as f:
        f.write(msg)
        msg_path = f.name
    try:
        res = _run_git(["commit", "-F", msg_path],
                       capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stdout or res.stderr)
            raise ReleaseError("HATA: git commit başarısız.")
    finally:
        Path(msg_path).unlink(missing_ok=True)
    print(f"[5/7] git commit → v{new}")


def _git_tag_version(new: str) -> None:
    """Zincir tamamsa açıklamalı sürüm etiketi atar."""
    msg_file = ROOT / ".git" / "TAG_MSG.txt"
    msg_file.write_text(f"JARVIS v{new}\n", encoding="utf-8", newline="\n")
    res = _run_git(["tag", "-a", f"v{new}", "-F", str(msg_file)],
                   capture_output=True, text=True)
    msg_file.unlink(missing_ok=True)
    if res.returncode != 0:
        print(res.stdout or res.stderr)
        raise ReleaseError("HATA: git etiketi atılamadı.")
    print(f"[7/7] git tag → v{new}")



def build_artifacts() -> None:
    """Dağıtım derlemesi: build_installer.py (senkron + PyInstaller + ISCC)."""
    print("[6/7] Dağıtım derlemesi (build_installer.py) ...")
    res = _run([sys.executable, "build_installer.py"],
               capture_output=True, text=True)
    if res.returncode != 0:
        print((res.stdout or "")[-2000:])
        print((res.stderr or "")[-2000:])
        raise ReleaseError("HATA: dağıtım derlemesi başarısız — etiket atılmadı.")
    print("      derleme: OK")


def main() -> None:
    """CLI akışı: kapı → sürüm → changelog → commit → derleme → etiket."""
    _configure_stdio()
    parser = argparse.ArgumentParser(
        description="JARVIS sürüm çıkarma otomasyonu")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--bump", choices=["patch", "minor", "major"],
                       help="sürüm kademesi (10.0.0 → patch: 10.0.1)")
    group.add_argument("--version", help="açık hedef sürüm (ör. 11.0.0)")
    parser.add_argument("--notes", help="CHANGELOG özet metni")
    parser.add_argument("--notes-file", type=Path,
                        help="CHANGELOG özeti dosyadan (Türkçe için güvenli)")
    parser.add_argument("--skip-build", action="store_true",
                        help="dağıtım derlemesini atla (commit + etiket)")
    parser.add_argument("--dry-run", action="store_true",
                        help="önizleme: hiçbir şey yazmaz/commit etmez")
    args = parser.parse_args()

    current = read_current_version()
    target = compute_next_version(current, args.bump, args.version)
    notes = (args.notes_file.read_text(encoding="utf-8").strip()
             if args.notes_file else args.notes)
    print(f"Sürüm: {current} → {target}"
          + ("  [DRY-RUN]" if args.dry_run else ""))
    if args.dry_run:
        print("Önizleme tamam — hiçbir dosya değiştirilmedi.")
        return

    dirty = _run_git(["status", "--porcelain"], capture_output=True, text=True)
    if dirty.stdout.strip():
        print(dirty.stdout)
        raise ReleaseError("HATA: çalışma ağacı kirli — önce commit edin "
                           "veya değişiklikleri saklayın.")

    run_gate()
    update_config_version(target)
    import build_installer  # yerel modül: sürüm senkron fonksiyonu
    build_installer.sync_installer_version(target)
    print(f"[2/7] installer.iss → MyAppVersion {target}")
    write_changelog(target, notes)
    _git_commit_version(target)
    if not args.skip_build:
        build_artifacts()
    _git_tag_version(target)
    print(f"\nOK: v{target} hazır. Yayınlamak için: git push --follow-tags")


if __name__ == "__main__":
    main()
