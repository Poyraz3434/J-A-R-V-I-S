"""Özellik 2 — Tek codebase, platform soyutlama katmanı (Windows + macOS).

KURAL: "Jarvis Windows" / "Jarvis macOS" diye AYRI ürünler YOK. Platform farkı
yalnızca runtime'da ``platform.system()`` ile tespit edilir ve bu modüldeki
ortak ``PlatformService`` arayüzü üzerinden yönetilir; ana uygulama kodu
platformdan bağımsız kalır.

ENVANTER — kod tabanında tespit edilen platforma özgü noktalar:
 1. services/computer_control.py: ``os.startfile`` (Windows ayar sayfası açma)
 2. services/computer_control.py: pygetwindow (pencere listesi/aktif pencere)
 3. services/computer_control.py + screen_watcher.py: mss ekran görüntüsü
    (macOS'ta "Ekran Kaydı" izni gerekir)
 4. services/computer_control.py: pyautogui tıkla/yaz (macOS'ta Accessibility)
 5. services/troubleshoot_agent.py: PowerShell Get-WinEvent / Win32_Startup
    (platform guard'lı ✓ — macOS'ta çalışmaz, boş döner)
 6. services/browser.py ``_open_allowed``: https allowlist (çapraz platform ✓)
 7. config.py: ``~/.jarvis`` yolları pathlib ile (çapraz platform ✓)
 8. Otomatik başlatma: Windows → Startup klasörü; macOS → LaunchAgent (bu modül)

PAKETLEME NOTU: Kaynak kodu TEK'tir; dağıtılabilir uygulama (.exe / .app)
her platform için ayrı derlenir (PyInstaller). Bu teknik bir zorunluluktur,
"ayrı sürüm" sayılmaz — önemli olan kaynak kodu ve kullanıcı deneyiminin tek olması.

İLK ÇALIŞTIRMA (macOS): Accessibility + Ekran Kaydı izinleri için
``maybe_show_permissions_guide`` yönlendirme ekranı gösterilir.
"""
from __future__ import annotations

import logging
import os
import platform
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class PlatformService:
    """Tüm platformların uyması gereken ortak arayüz (ana kod bunu çağırır)."""

    name = "unknown"

    # ── Ayarlar / dosya / url ───────────────────────────────────────────────
    def open_settings(self, section: str = "") -> str:
        """İşletim sistemi ayar sayfasını aç."""
        raise NotImplementedError

    def show_file(self, path) -> str:
        """Dosyayı sistem varsayılan uygulamasıyla aç/göster."""
        p = Path(path).expanduser()
        if not p.exists():
            return f"Dosya bulunamadı: {p}"
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(p))          # type: ignore[attr-defined]
            else:
                subprocess.Popen(["open", str(p)])
            return f"Açıldı: {p}"
        except Exception as exc:
            logger.warning("[Platform] show_file hatası: %s", exc)
            return f"Açılamadı ({exc}) — dosya yolu: {p}"

    def open_url(self, url: str) -> str:
        """URL'yi varsayılan tarayıcıda aç (allowlist çağrıları dışarısı)."""
        try:
            import webbrowser
            webbrowser.open(url)
            return f"Tarayıcıda açıldı: {url}"
        except Exception as exc:
            return f"URL açılamadı: {exc}"

    # ── Otomatik başlatma ──────────────────────────────────────────────────
    def startup_entries(self) -> list[str]:
        """Otomatik başlatma girdileri (listeleme)."""
        return []

    def set_auto_start(self, enable: bool) -> str:
        """Uygulamayı otomatik başlatmaya ekle/kaldır."""
        return "Otomatik başlatma bu platformda desteklenmiyor."

    def auto_start_enabled(self) -> bool:
        """Otomatik başlatma şu anda açık mı? (varsayılan: hayır)"""
        return False

    # ── İzinler (ilk çalıştırma yönlendirmesi) ─────────────────────────────
    def permissions_needed(self) -> list[dict]:
        """[{\"title\", \"why\", \"how\", \"settings_url\"}] — macOS'ta dolu."""
        return []

    def accessibility_status(self) -> str:
        """Erişilebilirlik izni özeti (bilgilendirme metni)."""
        return "Bu platformda ek izin gerekmiyor."


class WindowsPlatformService(PlatformService):
    """Windows: ms-settings, Startup klasörü, ek izin gerekmez."""

    name = "windows"

    def open_settings(self, section: str = "") -> str:
        try:
            from services.computer_control import open_windows_settings
            return open_windows_settings(section)
        except Exception as exc:
            return f"Windows ayarları açılamadı: {exc}"

    def startup_entries(self) -> list[str]:
        if not sys.platform.startswith("win"):
            return []
        try:
            ps = ("Get-CimInstance Win32_StartupCommand | "
                  "Select-Object Name,Location | ConvertTo-Json")
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=12)
            if r.returncode != 0 or not r.stdout.strip():
                return []
            import json
            items = json.loads(r.stdout)
            if isinstance(items, dict):
                items = [items]
            return [str(i.get("Name", "?")) for i in items[:20]]
        except Exception as exc:
            logger.warning("[Platform] Başlangıç listesi okunamadı: %s", exc)
            return []

    @staticmethod
    def _startup_shortcut():
        """Windows Başlangıç klasöründeki JARVIS kısayolu."""
        return (Path.home() / "AppData" / "Roaming" / "Microsoft" /
                "Windows" / "Start Menu" / "Programs" / "Startup" /
                "JARVIS.lnk")

    def auto_start_enabled(self) -> bool:
        try:
            return self._startup_shortcut().exists()
        except OSError:
            return False

    def set_auto_start(self, enable: bool) -> str:
        """Başlangıç klasörüne kısayol koy/kaldır (kullanıcı düzeyinde)."""
        try:
            target = self._startup_shortcut()
            if not enable:
                if target.exists():
                    target.unlink()
                return "Otomatik başlatma kapatıldı."
            exe = sys.executable
            script = str(Path(sys.argv[0]).resolve())
            ps = (
                "$ws = New-Object -ComObject WScript.Shell; "
                f"$s = $ws.CreateShortcut('{target}'); "
                f"$s.TargetPath = '{exe}'; "
                f"$s.Arguments = '{script}'; $s.Save()")
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=12)
            if r.returncode != 0:
                return f"Otomatik başlatma eklenemedi: {r.stderr[:120]}"
            return f"Otomatik başlatma eklendi: {target.name}"
        except Exception as exc:
            return f"Otomatik başlatma hatası: {exc}"

    def accessibility_status(self) -> str:
        return "Windows'ta ek erişilebilirlik izni gerekmez (varsayılan açık)."


class MacPlatformService(PlatformService):
    """macOS: System Settings URL'leri, LaunchAgents, TCC izin rehberi."""

    name = "macos"

    _SECTION_URLS = {
        "": "x-apple.systempreferences:com.apple.preference.security",
        "accessibility": "x-apple.systempreferences:"
                         "com.apple.preference.security?Privacy_Accessibility",
        "screen": "x-apple.systempreferences:"
                  "com.apple.preference.security?Privacy_ScreenCapture",
        "automation": "x-apple.systempreferences:"
                      "com.apple.preference.security?Privacy_Automation",
    }

    def open_settings(self, section: str = "") -> str:
        url = self._SECTION_URLS.get(
            (section or "").lower().strip(), self._SECTION_URLS[""])
        try:
            subprocess.Popen(["open", url])
            return f"Sistem Ayarları açıldı: {section or 'Gizlilik'}"
        except Exception as exc:
            return f"Sistem Ayarları açılamadı: {exc}"

    def startup_entries(self) -> list[str]:
        try:
            agent_dir = Path.home() / "Library" / "LaunchAgents"
            return sorted(p.stem for p in agent_dir.glob("*.plist"))[:20]
        except Exception:
            return []

    @staticmethod
    def _launch_agent_plist():
        """macOS LaunchAgent plist yolu (otomatik başlatma)."""
        return (Path.home() / "Library" / "LaunchAgents" /
                "com.jarvis.agent.plist")

    def auto_start_enabled(self) -> bool:
        try:
            return self._launch_agent_plist().exists()
        except OSError:
            return False

    def set_auto_start(self, enable: bool) -> str:
        """LaunchAgent plist'i yaz/sil (otomatik başlatma)."""
        try:
            plist = self._launch_agent_plist()
            if not enable:
                if plist.exists():
                    plist.unlink()
                return "Otomatik başlatma kapatıldı."
            plist.parent.mkdir(parents=True, exist_ok=True)
            exe = sys.executable
            script = str(Path(sys.argv[0]).resolve())
            plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.jarvis.agent</string>
<key>ProgramArguments</key><array>
<string>{exe}</string><string>{script}</string></array>
<key>RunAtLoad</key><true/>
</dict></plist>""", encoding="utf-8")
            return f"Otomatik başlatma eklendi: {plist.name}"
        except Exception as exc:
            return f"Otomatik başlatma hatası: {exc}"

    def permissions_needed(self) -> list[dict]:
        """İlk çalıştırmada gerekecek macOS izinleri (yönlendirme ekranı)."""
        return [
            {"title": "Erişilebilirlik (Accessibility)",
             "why": "ATLAS'ın klavye/fare kontrolü için zorunlu.",
             "how": "Sistem Ayarları → Gizlilik ve Güvenlik → Erişilebilirlik "
                    "→ JARVIS'i ekleyin ve açın.",
             "settings_url": self._SECTION_URLS["accessibility"]},
            {"title": "Ekran Kaydı (Screen Recording)",
             "why": "Screen watcher/OCR için ekran görüntüsü okuma gerekir.",
             "how": "Sistem Ayarları → Gizlilik ve Güvenlik → Ekran Kaydı → "
                    "JARVIS'i açın.",
             "settings_url": self._SECTION_URLS["screen"]},
        ]

    def accessibility_status(self) -> str:
        return ("macOS: Accessibility + Ekran Kaydı izinleri ilk çalıştırmada "
                "gerekebilir (rehber ekranına bakın).")


# ── Fabrika (ana kod yalnızca bunu çağırır) ────────────────────────────────
_service_instance: PlatformService | None = None


def get_platform_service() -> PlatformService:
    """Runtime'da platform tespiti → tek instance (singleton)."""
    global _service_instance
    if _service_instance is None:
        if platform.system() == "Darwin":
            _service_instance = MacPlatformService()
        else:
            _service_instance = WindowsPlatformService()
        logger.info("[Platform] Aktif servis: %s", _service_instance.name)
    return _service_instance


def maybe_show_permissions_guide(parent=None, settings=None,
                                 settings_save_fn=None) -> bool:
    """macOS ilk çalıştırmada izin rehberini BİR KEZ göster (Qt dialog)."""
    try:
        if get_platform_service().name != "macos":
            return False
        if settings is not None and settings.get("macos_guide_shown"):
            return False
        from PySide6.QtWidgets import (
            QDialog, QDialogButtonBox, QLabel, QTextEdit, QVBoxLayout,
        )
        dlg = QDialog(parent)
        dlg.setWindowTitle("JARVIS — macOS İzinleri (İlk Çalıştırma)")
        dlg.setMinimumWidth(560)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(
            "ATLAS ve ekran özellikleri için aşağıdaki izinleri verin:"))
        body = QTextEdit()
        body.setReadOnly(True)
        lines = []
        for perm in get_platform_service().permissions_needed():
            lines.append(f"• {perm['title']}\n  Neden: {perm['why']}\n"
                         f"  Nasıl: {perm['how']}\n")
        body.setPlainText("\n".join(lines))
        layout.addWidget(body)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dlg.accept)
        layout.addWidget(buttons)
        dlg.exec()
        if settings is not None:
            settings["macos_guide_shown"] = True
            if settings_save_fn:
                settings_save_fn(settings)
        return True
    except Exception as exc:
        logger.warning("[Platform] İzin rehberi gösterilemedi: %s", exc)
        return False
