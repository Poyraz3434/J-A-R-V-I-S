"""Source and frozen-package integrity checks."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

from logger_setup import logger

_FROZEN_IMPORTS = (
    "PySide6.QtWidgets",
    "requests",
    "services.network",
    "services.currency",
    "services.ai_engine",
    "services.skill_registry",
    "services.task_center",
    "services.update_check",
    "services.data_backup",
    "services.startup_diagnostics",
)


def validate_source_package(root: str | Path) -> list[str]:
    """Return source packaging errors without invoking PyInstaller."""
    root = Path(root)
    required_files = (
        root / "main.py",
        root / "jarvis.spec",
        root / "JARVIS.ico",
        root / "data" / "curriculum.json",
        root / "services" / "ai_engine.py",
    )
    errors = [f"Gerekli paketleme girdisi bulunamadı: {path}" for path in required_files if not path.is_file()]
    spec_path = root / "jarvis.spec"
    if spec_path.is_file():
        spec = spec_path.read_text(encoding="utf-8-sig")
        if "data/curriculum.json" not in spec:
            errors.append("jarvis.spec curriculum.json veri dosyasını bundle etmiyor.")
        if '".env"' in spec or "('.env'," in spec:
            errors.append("jarvis.spec içinde .env paketlemeye eklenmiş görünüyor.")
        if '"requests"' not in spec and "'requests'" not in spec:
            errors.append("jarvis.spec içinde dinamik requests import girdisi yok.")
    return errors


def validate_frozen_layout(package_dir: str | Path) -> list[str]:
    """Check the stable onedir layout produced by jarvis.spec."""
    package_dir = Path(package_dir)
    required_files = (
        package_dir / "JARVIS.exe",
        package_dir / "_internal" / "data" / "curriculum.json",
    )
    return [
        f"Paket çıktısında gerekli dosya bulunamadı: {path}"
        for path in required_files
        if not path.is_file()
    ]


def frozen_runtime_check() -> bool:
    """Import critical runtime modules and verify bundled data inside the EXE."""
    if not getattr(sys, "frozen", False):
        logger.error("[PackageCheck] Frozen self-test yalnızca paketli exe'de çalışır.")
        return False
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    curriculum = bundle_root / "data" / "curriculum.json"
    if not curriculum.is_file():
        logger.error("[PackageCheck] Müfredat verisi bulunamadı: %s", curriculum)
        return False
    try:
        for module_name in _FROZEN_IMPORTS:
            importlib.import_module(module_name)
    except Exception:
        logger.exception("[PackageCheck] Gerekli paket import edilemedi: %s", module_name)
        return False
    logger.info("[PackageCheck] Frozen uygulama kaynakları ve temel importlar doğrulandı.")
    return True
