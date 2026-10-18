"""Dosya transferi uçları — telefon <-> PC paylaşım klasörü.

Güvenlik (integrations/files.py içinde): yol kaçışı engelli, ad sanitizeli,
silme ucu yok, 100 MB sınırı.
"""
from __future__ import annotations

import logging
import urllib.parse

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from ..core import counters
from ..integrations import files as files_module
from ..store import database

logger = logging.getLogger("jarvis.api.files")

router = APIRouter()


@router.get("/api/files")
def list_files() -> dict:
    return files_module.list_files()


@router.post("/api/files/upload")
async def upload_file(file: UploadFile = File(...)) -> dict:
    if file.size is not None and file.size > files_module.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Dosya 100 MB sınırını aşıyor.")
    data = await file.read(files_module.MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=422, detail="Boş dosya.")
    if len(data) > files_module.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Dosya 100 MB sınırını aşıyor.")
    try:
        result = files_module.write_file(file.filename or "dosya", data)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    counters.bump_command_count()
    database.audit("files.upload", detail=result["name"])
    return result


@router.get("/api/files/download")
def download_file(name: str = Query(...)) -> FileResponse:
    safe = files_module.sanitize_name(name)
    try:
        data_path = files_module.shared_dir() / safe
        resolved = files_module.read_file(safe)
        _ = len(resolved)  # okunabilirlik kontrolü
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    database.audit("files.download", detail=safe)
    return FileResponse(
        data_path,
        filename=safe,
        media_type="application/octet-stream",
    )
