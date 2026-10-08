"""Özellik 5 — Dosya Format Dönüştürücü (PDF / JPG / PNG / Metin).

Desteklenen dönüşümler:
  * JPG/PNG → PDF        (Pillow)
  * PDF → JPG/PNG        (PyMuPDF; çok sayfalı → sayfa sırası korunur, zip'lenir)
  * PDF → TXT            (PyMuPDF; metin katmanı yoksa OCR tespiti → pytesseract)
  * JPG ↔ PNG            (Pillow)

Kenar durumları: bozuk/şifreli PDF → anlamlı hata; desteklenmeyen format →
desteklenen listesi; OCR gereksinimi otomatik tespit edilir.
"""
from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_HINT = (
    "Desteklenen dönüşümler: JPG/PNG → PDF, PDF → JPG/PNG, PDF → TXT "
    "(OCR destekli), JPG ↔ PNG."
)
_PNG_JPG = {".png", ".jpg", ".jpeg"}
_KNOWN = _PNG_JPG | {".pdf", ".txt"}
_ALIASES = {"text": "txt", "jpeg": "jpg"}


@dataclass
class ConvertResult:
    """Dönüşüm sonucu — UI mesajı + üretilen dosyalar."""

    ok: bool
    message: str
    outputs: list[str] = field(default_factory=list)
    ocr_needed: bool = False


def _norm(fmt: str) -> str:
    f = (fmt or "").lower().lstrip(".")
    return _ALIASES.get(f, f)


def _same_format(src_ext: str, target: str) -> bool:
    """Kaynak ve hedef aynı formatta mı?"""
    if src_ext == ".pdf":
        return target == "pdf"
    if src_ext == ".png":
        return target == "png"
    if src_ext in (".jpg", ".jpeg"):
        return target == "jpg"
    if src_ext == ".txt":
        return target == "txt"
    return False


def detect_ocr_needed(pdf_path) -> bool:
    """PDF'de metin katmanı yoksa (taranmış) OCR gerekir → True."""
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        try:
            for page in doc:
                if page.get_text().strip():
                    return False
            return doc.page_count > 0
        finally:
            doc.close()
    except Exception as exc:
        logger.warning("[Converter] OCR tespiti başarısız: %s", exc)
        return False


def _pdf_to_text(src: Path, out: Path) -> ConvertResult:
    try:
        import fitz
        doc = fitz.open(str(src))
    except Exception as exc:
        return ConvertResult(
            False, f"PDF açılamadı — bozuk veya şifreli olabilir. ({exc})")
    try:
        text = "".join(page.get_text() for page in doc)
        ocr_needed = not text.strip() and doc.page_count > 0
        used_ocr = False
        if ocr_needed:
            try:
                import pytesseract
                from PIL import Image
                parts = []
                for page in doc:
                    pix = page.get_pixmap(dpi=200)
                    img = Image.frombytes(
                        "RGB", (pix.width, pix.height), pix.samples)
                    parts.append(pytesseract.image_to_string(img, lang="tur+eng"))
                text = "\n".join(parts)
                used_ocr = bool(text.strip())
            except Exception as ocr_exc:
                logger.info("[Converter] OCR çalıştırılamadı: %s", ocr_exc)
        out.write_text(text, encoding="utf-8")
        if ocr_needed and not used_ocr:
            return ConvertResult(
                True,
                f"PDF taranmış (metin katmanı yok); OCR gerekli fakat "
                f"çalıştırılamadı — çıktı eksik olabilir: {out.name}",
                [str(out)], ocr_needed=True)
        suffix = " (OCR ile okundu)" if used_ocr else ""
        return ConvertResult(True, f"PDF → TXT tamam{suffix}: {out.name}",
                             [str(out)])
    finally:
        doc.close()


def _pdf_to_images(src: Path, out_dir: Path, fmt: str = "png") -> ConvertResult:
    """PDF → görseller; sayfa sırası korunur, çokluysa zip'lenir."""
    try:
        import fitz
        doc = fitz.open(str(src))
    except Exception as exc:
        return ConvertResult(
            False, f"PDF açılamadı — bozuk veya şifreli olabilir. ({exc})")
    try:
        outputs = []
        for i, page in enumerate(doc, 1):
            pix = page.get_pixmap(dpi=150)
            target = out_dir / f"{src.stem}_p{i:03d}.{fmt}"
            pix.save(str(target))
            outputs.append(str(target))
        if not outputs:
            return ConvertResult(False, "PDF'de sayfa bulunamadı.")
        if len(outputs) == 1:
            return ConvertResult(
                True, f"PDF → {fmt.upper()} tamam: {Path(outputs[0]).name}",
                outputs)
        zip_path = out_dir / f"{src.stem}_{fmt}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in outputs:
                zf.write(p, Path(p).name)
        return ConvertResult(
            True,
            f"PDF → {len(outputs)} {fmt.upper()} (sayfa sırası korunup zip'lendi): "
            f"{zip_path.name}", [str(zip_path)] + outputs)
    finally:
        doc.close()


def convert_file(src, target: str, out_dir=None) -> ConvertResult:
    """``src`` dosyasını ``target`` formatına çevir (hatalar anlamlı mesajla)."""
    src = Path(src).expanduser()
    target = _norm(target)
    if not src.exists():
        return ConvertResult(False, f"Dosya bulunamadı: {src}")
    if target not in {"pdf", "png", "jpg", "txt"}:
        return ConvertResult(
            False, f"'{target}' hedef formatı desteklenmiyor. {SUPPORTED_HINT}")
    src_ext = src.suffix.lower()
    if src_ext not in _KNOWN:
        return ConvertResult(
            False,
            f"'{src_ext or '?'}' kaynak formatı desteklenmiyor. {SUPPORTED_HINT}")
    if _same_format(src_ext, target):
        return ConvertResult(True, f"Dosya zaten '{target}' formatında: {src.name}")
    out_dir = Path(out_dir).expanduser() if out_dir else src.parent / "converted"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        if src_ext == ".pdf" and target == "txt":
            return _pdf_to_text(src, out_dir / f"{src.stem}.txt")
        if src_ext == ".pdf" and target in {"png", "jpg"}:
            return _pdf_to_images(src, out_dir, target)
        if src_ext in _PNG_JPG and target == "pdf":
            from PIL import Image
            out = out_dir / f"{src.stem}.pdf"
            with Image.open(src) as img:
                img.convert("RGB").save(out, "PDF")
            return ConvertResult(
                True, f"{src_ext[1:].upper()} → PDF tamam: {out.name}",
                [str(out)])
        if src_ext in _PNG_JPG and target in {"png", "jpg"}:
            from PIL import Image
            out = out_dir / f"{src.stem}.{target}"
            with Image.open(src) as img:
                rgb = img.convert("RGB") if target == "jpg" else img
                rgb.save(out, "PNG" if target == "png" else "JPEG", quality=92)
            return ConvertResult(
                True,
                f"{src_ext[1:].upper()} → {target.upper()} tamam: {out.name}",
                [str(out)])
        if src_ext == ".txt":
            return ConvertResult(
                False,
                f"TXT → {target.upper()} dönüşümü desteklenmiyor. {SUPPORTED_HINT}")
        return ConvertResult(False, f"Bu kombinasyon desteklenmiyor. {SUPPORTED_HINT}")
    except Exception as exc:
        logger.exception("[Converter] Dönüşüm hatası")
        return ConvertResult(False, f"Dönüşüm başarısız: {exc}")
