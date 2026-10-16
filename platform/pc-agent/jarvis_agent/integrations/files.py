"""Dosya transferi — yerel ağ paylaşım klasörü (Faz 5).

Güvenlik:
- Yalnızca JARVIS_FILES_DIR (varsayılan ~/JarvisFiles) içinde çalışır.
- Path traversal koruması: resolve + is_relative_to kontrolü.
- Dosya adı sanitizasyonu: yol ayracı ve gizli dosya karakterleri temizlenir.
- Silme uçları yoktur; yükleme yalnızca açık POST ile yapılır.
"""
from __future__ import annotations

import datetime
import os
import re
import pathlib
from .. import config

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._\- \u00C0-\u024F\u0600-\u06FF]+")
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB


def shared_dir() -> pathlib.Path:
    raw = config.env("JARVIS_FILES_DIR", "") or os.path.join(
        os.path.expanduser("~"), "JarvisFiles"
    )
    path = pathlib.Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve(name: str) -> pathlib.Path:
    """Adı paylaşım klasörü içinde güvenli biçimde çözer; kaçışa izin vermez."""
    base = shared_dir().resolve()
    candidate = (base / name).resolve()
    if not candidate.is_relative_to(base):
        raise PermissionError("Bu yol paylaşım klasörünün dışına çıkıyor.")
    return candidate


def sanitize_name(name: str) -> str:
    base = os.path.basename(name or "dosya")
    cleaned = _SAFE_NAME.sub("_", base).strip(" ._")
    return cleaned[:120] or "dosya"


def list_files() -> dict:
    base = shared_dir()
    items: list[dict] = []
    for entry in sorted(base.iterdir(), key=lambda p: p.name.lower()):
        if entry.is_file():
            stat = entry.stat()
            items.append(
                {
                    "name": entry.name,
                    "size": stat.st_size,
                    "modified": datetime.datetime.fromtimestamp(
                        stat.st_mtime
                    ).isoformat(timespec="seconds"),
                }
            )
    return {"available": True, "directory": str(base), "files": items}


def read_file(name: str) -> bytes:
    path = _resolve(name)
    if not path.is_file():
        raise FileNotFoundError(f"'{name}' bulunamadı.")
    return path.read_bytes()


def write_file(name: str, data: bytes) -> dict:
    safe = sanitize_name(name)
    path = _resolve(safe)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Dosya 100 MB sınırını aşıyor.")
    path.write_bytes(data)
    return {"name": path.name, "size": len(data)}


def stage_from_pc(source_path: str) -> dict:
    """PC'deki bir dosyayı paylaşım klasörüne kopyalar (LLM send_file aracı).

    Güvenlik: kaynak yalnızca OKUNUR; hedef daima shared_dir içinde
    sanitize edilmiş addır; 100 MB sınırı geçerlidir.
    """
    raw = str(source_path or "").strip().strip('"')
    if not raw:
        raise ValueError("Kaynak dosya yolu boş olamaz.")
    src = pathlib.Path(raw).expanduser()
    if not src.is_absolute():
        src = pathlib.Path.cwd() / src
    src = src.resolve()
    base = shared_dir().resolve()
    if src == base or base in src.parents:
        raise ValueError("Dosya zaten paylaşım klasöründe.")
    if not src.is_file():
        raise FileNotFoundError(f"'{src.name}' bulunamadı.")
    if src.stat().st_size > MAX_UPLOAD_BYTES:
        raise ValueError("Dosya 100 MB sınırını aşıyor.")
    data = src.read_bytes()
    result = write_file(src.name, data)
    return {**result, "source": str(src)}


def available() -> bool:
    return True
