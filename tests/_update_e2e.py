"""Gerçek HTTPS üzerinden güncelleme denetimi el testi (Özellik: update check).

unittest discover'a girmez (``_`` öneki — ``tests/_smoke.py`` deseni).
Kullanım:
    python tests/_update_e2e.py

Genel bir GitHub 'latest release' manifestine GERÇEK ağ isteği yapar;
URL doğrulama, TLS, JSON çözümleme, sürüm ayrıştırma ve karşılaştırma
zincirinin tamamının canlı çalıştığını doğrular. Kaynak projenin sürümü
JARVIS'in sürümü olmadığından `update_available` sonucu bilgi amaçlıdır.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import APP_VERSION  # noqa: E402
from services.update_check import check_for_update  # noqa: E402

# Gerçek, herkese açık HTTPS manifest: PyInstaller'ın son yayını (GitHub API).
MANIFEST_URL = "https://api.github.com/repos/pyinstaller/pyinstaller/releases/latest"


def main() -> int:
    try:
        info = check_for_update(manifest_url=MANIFEST_URL)
    except Exception as exc:  # ağ/TLS/JSON hatası tek satırda raporlanır
        print(f"E2E-FAIL: {exc}")
        return 1
    if not info.latest_version or not info.release_url.startswith("https://"):
        print(f"E2E-FAIL: alanlar bozuk — {info!r}")
        return 1
    print(
        f"E2E-OK latest={info.latest_version} current={APP_VERSION} "
        f"available={info.update_available} url={info.release_url[:60]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
