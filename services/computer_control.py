"""Bounded Windows computer-control helpers.

Read-only inspection is available by default. Mutating UI actions require an
explicit confirmation in the caller and are restricted to the active screen.
"""
from __future__ import annotations

import glob
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

APP_DATA_DIR = Path.home() / ".jarvis"
SCREENSHOT_DIR = APP_DATA_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_APPS = {
    "notepad": ["notepad.exe"],
    "hesap makinesi": ["calc.exe"],
    "calculator": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "boya": ["mspaint.exe"],
    "dosya gezgini": ["explorer.exe"],
    "explorer": ["explorer.exe"],
    "chrome": ["chrome.exe"],
    "google chrome": ["chrome.exe"],
    "google chrome browser": ["chrome.exe"],
    "edge": ["msedge.exe"],
    "microsoft edge": ["msedge.exe"],
    "visual studio code": ["code.cmd"],
    "vs code": ["code.cmd"],
}

WINDOWS_APP_PATHS = {
    "chrome": [
        Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ],
    "google chrome": [
        Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ],
    "edge": [Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe"],
    "microsoft edge": [Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe"],
}


def list_open_windows() -> str:
    try:
        import pygetwindow as gw
        titles = [title.strip() for title in gw.getAllTitles() if title.strip()]
    except ImportError:
        return "Açık pencere analizi için pygetwindow gerekli."
    except Exception as exc:
        return f"Açık pencereler okunamadı: {exc}"
    if not titles:
        return "Açık pencere başlığı bulunamadı."
    return "Açık pencereler:\n" + "\n".join(f"- {title}" for title in titles[:30])


def system_processes() -> str:
    try:
        import psutil
        rows = []
        for process in psutil.process_iter(["name", "cpu_percent", "memory_percent"]):
            info = process.info
            rows.append((info.get("cpu_percent") or 0, info.get("name") or "?", info.get("memory_percent") or 0))
        rows.sort(reverse=True)
        return "En yoğun işlemler:\n" + "\n".join(
            f"- {name}: CPU %{cpu:.1f}, RAM %{memory:.1f}" for cpu, name, memory in rows[:10]
        )
    except ImportError:
        return "İşlem analizi için psutil gerekli."
    except Exception as exc:
        return f"İşlem listesi okunamadı: {exc}"


def capture_screen() -> str:
    try:
        import mss
        import mss.tools
        with mss.mss() as screen:
            shot = screen.grab(screen.monitors[0])
            target = SCREENSHOT_DIR / "latest.png"
            mss.tools.to_png(shot.rgb, shot.size, output=str(target))
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
        return "Ekran görüntüsü kaydedildi."
    except ImportError:
        return "Ekran analizi için mss gerekli."
    except Exception as exc:
        return f"Ekran görüntüsü alınamadı: {exc}"


def analyze_screen() -> str:
    """Capture the screen and extract visible text when local OCR is available."""
    capture_result = capture_screen()
    if not capture_result.startswith("Ekran görüntüsü kaydedildi"):
        return capture_result
    target = SCREENSHOT_DIR / "latest.png"
    try:
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(target), lang="tur+eng").strip()
        if not text:
            return "Ekran görüntüsü alındı ancak okunabilir metin bulunamadı."
        return f"Ekran metni:\n{text[:4000]}"
    except ImportError:
        return f"{capture_result}\nGörsel metin analizi için pytesseract ve Pillow gerekli."
    except Exception as exc:
        return f"Ekran alındı fakat OCR analizi başarısız: {exc}"


def open_allowed_app(app_name: str) -> str:
    key = " ".join((app_name or "").lower().split())
    key = re.sub(r"['’]?[ıiuü]$", "", key).strip()
    key = re.sub(r"^(the|uygulama|program)\s+", "", key).strip()
    command = ALLOWED_APPS.get(key)
    if not command:
        return "Bu uygulama allowlist içinde değil. Önce güvenli uygulama listesine ekleyin."
    try:
        candidates = WINDOWS_APP_PATHS.get(key, [])
        executable = next((str(path) for path in candidates if path.is_file()), command[0])
        command = [executable, *command[1:]]
        subprocess.Popen(command, shell=False, close_fds=True)
        return f"Uygulama açıldı: {key}"
    except FileNotFoundError:
        return f"Uygulama bulunamadı: {key}"
    except OSError as exc:
        return f"Uygulama açılamadı: {exc}"


def active_window_title() -> str:
    try:
        import pygetwindow as gw
        window = gw.getActiveWindow()
        return window.title if window else "Aktif pencere bulunamadı."
    except ImportError:
        return "Aktif pencere analizi için pygetwindow gerekli."
    except Exception as exc:
        return f"Aktif pencere okunamadı: {exc}"


def click_screen(x: int, y: int) -> str:
    try:
        x, y = int(x), int(y)
    except (TypeError, ValueError):
        return "Koordinatlar geçersiz."
    if not (0 <= x <= 10000 and 0 <= y <= 10000):
        return "Koordinatlar güvenlik sınırları dışında."
    try:
        import pyautogui
        pyautogui.click(x, y)
        return f"Ekranda tıklama yapıldı: ({x}, {y})"
    except ImportError:
        return "Tıklama için pyautogui gerekli."
    except Exception as exc:
        return f"Tıklama yapılamadı: {exc}"


def move_mouse(x: int, y: int) -> str:
    try:
        x, y = int(x), int(y)
    except (TypeError, ValueError):
        return "Koordinatlar geçersiz."
    if not (0 <= x <= 10000 and 0 <= y <= 10000):
        return "Koordinatlar güvenlik sınırları dışında."
    try:
        import pyautogui
        pyautogui.moveTo(x, y, duration=0.2)
        return f"Fare taşındı: ({x}, {y})"
    except ImportError:
        return "Fare kontrolü için pyautogui gerekli."
    except Exception as exc:
        return f"Fare taşınamadı: {exc}"


def type_text(text: str) -> str:
    text = str(text or "")[:500]
    if not text:
        return "Yazılacak metin boş."
    try:
        import pyautogui
        pyautogui.write(text, interval=0.01)
        return "Metin aktif pencereye yazıldı."
    except ImportError:
        return "Klavye kontrolü için pyautogui gerekli."
    except Exception as exc:
        return f"Metin yazılamadı: {exc}"


def platform_summary() -> str:
    return f"{platform.system()} {platform.release()} / {platform.machine()}"


def open_windows_settings(section: str = "") -> str:
    pages = {
        "": "ms-settings:",
        "wifi": "ms-settings:network-wifi",
        "ağ": "ms-settings:network-status",
        "ses": "ms-settings:sound",
        "ekran": "ms-settings:display",
        "bluetooth": "ms-settings:bluetooth",
        "uygulamalar": "ms-settings:appsfeatures",
    }
    target = pages.get(" ".join((section or "").lower().split()))
    if target is None:
        return "Bu Windows ayar sayfası allowlist içinde değil."
    try:
        os.startfile(target)
        return f"Windows ayarları açıldı: {section or 'ana sayfa'}"
    except (AttributeError, OSError) as exc:
        return f"Windows ayarları açılamadı: {exc}"


def edit_text_file(path: str, find_text: str, replacement: str) -> str:
    """Edit a small user-owned text file with a timestamped backup and atomic replace."""
    try:
        candidate = Path(path).expanduser().resolve(strict=True)
        home = Path.home().resolve()
        allowed_suffixes = {".txt", ".md", ".py", ".json", ".ini", ".cfg", ".yaml", ".yml"}
        if home not in candidate.parents or candidate.suffix.lower() not in allowed_suffixes:
            return "Dosya güvenlik sınırları dışında veya türü izinli değil."
        if candidate.stat().st_size > 5 * 1024 * 1024:
            return "Dosya 5 MB sınırını aşıyor."
        old_content = candidate.read_text(encoding="utf-8")
        if find_text not in old_content:
            return "Aranan metin dosyada bulunamadı; değişiklik yapılmadı."
        backup = candidate.with_name(f"{candidate.name}.jarvis-{time.time_ns()}.bak")
        shutil.copy2(candidate, backup)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{candidate.name}.jarvis-",
            suffix=".tmp",
            dir=candidate.parent,
            delete=False,
        ) as handle:
            temp = Path(handle.name)
            handle.write(old_content.replace(find_text, replacement, 1))
        try:
            os.replace(temp, candidate)
        finally:
            if temp.exists():
                temp.unlink()
        return f"Dosya güncellendi. Yedek oluşturuldu: {backup.name}"
    except UnicodeDecodeError:
        return "Yalnızca UTF-8 metin dosyaları düzenlenebilir."
    except (OSError, ValueError) as exc:
        return f"Dosya düzenlenemedi: {exc}"


def preview_text_edit(path: str, find_text: str, replacement: str) -> str:
    """Return a bounded before/after preview without changing the file."""
    try:
        candidate = Path(path).expanduser().resolve(strict=True)
        home = Path.home().resolve()
        allowed_suffixes = {".txt", ".md", ".py", ".json", ".ini", ".cfg", ".yaml", ".yml"}
        if home not in candidate.parents or candidate.suffix.lower() not in allowed_suffixes:
            return "Dosya güvenlik sınırları dışında veya türü izinli değil."
        if candidate.stat().st_size > 5 * 1024 * 1024:
            return "Dosya 5 MB sınırını aşıyor."
        content = candidate.read_text(encoding="utf-8")
        position = content.find(find_text)
        if position < 0:
            return "Aranan metin dosyada bulunamadı; değişiklik yapılmayacak."
        updated = content.replace(find_text, replacement, 1)
        before = content[max(0, position - 100):position + len(find_text) + 100]
        after = updated[max(0, position - 100):position + len(replacement) + 100]
        return (
            f"Dosya: {candidate.name}\n"
            f"Önce: {before[:400]}\n"
            f"Sonra: {after[:400]}\n"
            f"Durum: {'değişiklik uygulanacak' if updated != content else 'içerik aynı'}"
        )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return f"Önizleme oluşturulamadı: {exc}"


def undo_last_text_edit(path: str) -> str:
    """Restore the newest Jarvis backup for one eligible file under the home dir."""
    try:
        candidate = Path(path).expanduser().resolve(strict=True)
        home = Path.home().resolve()
        allowed_suffixes = {".txt", ".md", ".py", ".json", ".ini", ".cfg", ".yaml", ".yml"}
        if home not in candidate.parents or candidate.suffix.lower() not in allowed_suffixes:
            return "Dosya güvenlik sınırları dışında veya türü izinli değil."

        backups = sorted(
            (
                item
                for item in candidate.parent.glob(
                    f"{glob.escape(candidate.name)}.jarvis-*.bak"
                )
                if ".jarvis-undo-" not in item.name
            ),
            key=lambda backup: backup.stat().st_mtime_ns,
            reverse=True,
        )
        backup = next(
            (item for item in backups if item.is_file() and not item.is_symlink()),
            None,
        )
        if backup is None:
            return "Bu dosya için Jarvis yedeği bulunamadı."
        if backup.resolve().parent != candidate.parent:
            return "Yedek dosya güvenlik sınırları dışında."

        current_backup = candidate.with_name(
            f"{candidate.name}.jarvis-undo-{time.time_ns()}.bak"
        )
        shutil.copy2(candidate, current_backup)
        with tempfile.NamedTemporaryFile(
            prefix=f".{candidate.name}.jarvis-undo-",
            suffix=".tmp",
            dir=candidate.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
        try:
            shutil.copy2(backup, temporary)
            os.replace(temporary, candidate)
        finally:
            if temporary.exists():
                temporary.unlink()
        return f"Son Jarvis yedeği geri yüklendi. Mevcut sürüm yedeklendi: {current_backup.name}"
    except (OSError, ValueError) as exc:
        return f"Geri alma başarısız: {exc}"
