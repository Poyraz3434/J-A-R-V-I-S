"""
JARVIS v10 APEX PRIME — Plugin Yöneticisi
==========================================
Açılışta plugins/ klasörünü tarar, manifest.json doğrular,
handler.py import eder. Trigger keyword eşleşmesiyle çağırır.

Plugin yapısı:
    plugins/
      my_plugin/
        manifest.json  — isim, açıklama, triggers, requires
        handler.py     — handle(query: str, context: dict) -> str
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Optional

from logger_setup import logger

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"


class PluginManifest:
    def __init__(self, data: dict, plugin_dir: Path):
        self.name:        str       = data.get("name", "unnamed")
        self.version:     str       = data.get("version", "1.0")
        self.description: str       = data.get("description", "")
        self.triggers:    list[str] = [t.lower() for t in data.get("triggers", [])]
        self.requires:    list[str] = data.get("requires", [])
        self.author:      str       = data.get("author", "")
        self.enabled:     bool      = data.get("enabled", True)
        self.plugin_dir:  Path      = plugin_dir


class Plugin:
    def __init__(self, manifest: PluginManifest, handler_module):
        self.manifest = manifest
        self._handler = handler_module
        self.error: str = ""

    def matches(self, text: str) -> bool:
        """Kullanıcı metni bu plugin'in trigger'larından birini içeriyor mu?"""
        t = text.lower()
        return any(trigger in t for trigger in self.manifest.triggers)

    def handle(self, query: str, context: dict | None = None) -> str:
        """Plugin'i çalıştır."""
        try:
            return self._handler.handle(query, context or {})
        except Exception as exc:
            logger.error("[PluginManager] %s hata: %s", self.manifest.name, exc)
            return f"Plugin hatası ({self.manifest.name}): {exc}"


class PluginManager:
    """
    Plugin yöneticisi.
    
    Kullanım:
        pm = PluginManager()
        pm.load_all()
        result = pm.dispatch("hava durumu detaylı")
        if result is not None:
            print(result)  # Plugin yanıtı
    """

    def __init__(self, plugins_dir: Optional[Path] = None):
        self._plugins_dir = plugins_dir or PLUGINS_DIR
        self._plugins: list[Plugin] = []
        self._loaded = False

    def load_all(self) -> list[str]:
        """Tüm pluginleri yükler. Hatalı plugin sistemi çökertmez."""
        self._plugins = []
        if not self._plugins_dir.exists():
            logger.info("[PluginManager] plugins/ klasörü yok: %s", self._plugins_dir)
            return []

        loaded = []
        for plugin_dir in sorted(self._plugins_dir.iterdir()):
            if not plugin_dir.is_dir() or plugin_dir.name.startswith("_"):
                continue
            result = self._load_one(plugin_dir)
            if result:
                loaded.append(result)

        self._loaded = True
        logger.info("[PluginManager] %d plugin yüklendi: %s", len(loaded), loaded)
        return loaded

    def _load_one(self, plugin_dir: Path) -> Optional[str]:
        """Tek bir plugin yükler. Başarısızsa None döner."""
        manifest_path = plugin_dir / "manifest.json"
        handler_path  = plugin_dir / "handler.py"

        if not manifest_path.exists() or not handler_path.exists():
            return None

        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest_data = json.load(f)
            manifest = PluginManifest(manifest_data, plugin_dir)

            if not manifest.enabled:
                return None

            # Gereksinim kontrolü (opsiyonel, hata verme — sadece uyar)
            for req in manifest.requires:
                try:
                    __import__(req.replace("-", "_"))
                except ImportError:
                    logger.warning("[PluginManager] %s için '%s' kurulu değil — yüklenecek ama çalışmayabilir.",
                                   manifest.name, req)

            # Handler'ı dynamic import et
            spec = importlib.util.spec_from_file_location(
                f"jarvis_plugin_{manifest.name}", handler_path)
            module = importlib.util.module_from_spec(spec)
            # Plugin'in kendi dizinini sys.path'e ekle (kardeş modüller için)
            if str(plugin_dir) not in sys.path:
                sys.path.insert(0, str(plugin_dir))
            spec.loader.exec_module(module)

            if not hasattr(module, "handle"):
                logger.warning("[PluginManager] %s: handle() fonksiyonu yok.", manifest.name)
                return None

            plugin = Plugin(manifest, module)
            self._plugins.append(plugin)
            return manifest.name

        except Exception as exc:
            logger.error("[PluginManager] %s yüklenemedi: %s", plugin_dir.name, exc)
            return None

    def dispatch(self, text: str, context: dict | None = None) -> Optional[str]:
        """
        Kullanıcı metnini plugin'lere karşı kontrol eder.
        İlk eşleşen plugin'in yanıtını döndürür.
        Eşleşme yoksa None döndürür.
        """
        if not self._loaded:
            self.load_all()
        for plugin in self._plugins:
            if plugin.matches(text):
                logger.info("[PluginManager] Dispatch → %s", plugin.manifest.name)
                return plugin.handle(text, context)
        return None

    def list_plugins(self) -> str:
        """Yüklü pluginlerin listesi."""
        if not self._plugins:
            return "Yüklü plugin yok. plugins/ klasörüne yeni plugin ekleyebilirsiniz."
        lines = ["Yüklü Pluginler:"]
        for p in self._plugins:
            lines.append(
                f"  • {p.manifest.name} v{p.manifest.version} — {p.manifest.description}\n"
                f"    Tetikleyiciler: {', '.join(p.manifest.triggers[:5])}"
            )
        return "\n".join(lines)

    def reload(self) -> str:
        """Pluginleri yeniden yükler (sıcak yükleme)."""
        self._loaded = False
        self._plugins = []
        loaded = self.load_all()
        return f"{len(loaded)} plugin yeniden yüklendi: {', '.join(loaded) or 'yok'}"

    @property
    def plugin_count(self) -> int:
        return len(self._plugins)


# ── Singleton ────────────────────────────────────────────────────────────
_pm_instance: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    global _pm_instance
    if _pm_instance is None:
        _pm_instance = PluginManager()
        _pm_instance.load_all()
    return _pm_instance

