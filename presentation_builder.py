"""Özellik 1 — Otomatik Sunum Oluşturma (fallback zinciri).

Zincir (sırayla, biri tutmazsa sonrakine geç):
  1) python-pptx → .pptx   2) Canva API (anahtar yoksa atlanır)   3) PNG slayt seti
Hangi yöntem kullanıldı ``PresentationResult.method`` alanındadır; kullanıcıya
net bildirilir (atlanan adımların sebebi dahil).

Gereksinimler: başlık + içindekiler + içerik + kapanış slaytları; içerik slaytları
≤6 madde (aşarsa otomatik bölünür); kullanıcı konu/slayt sayısı/ton/hedef kitle alır
(varsayılan 9 slayt = 8-10 aralığı).
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_SLIDES = 9   # 8-10 aralığının ortası
MAX_BULLETS = 6      # slayt başına madde sınırı → aşarsa slayt bölünür
OUT_ROOT = Path.home() / ".jarvis" / "presentations"

_OUTLINE_INSTRUCTION = (
    "Bir sunum taslağı JSON'u üret (başka metin yazma): "
    '{"title": "Sunum başlığı", "slides": [{"title": "slayt başlığı", '
    '"bullets": ["madde1", "..."]}]} — {n} içerik slaytı; her slaytta en fazla '
    "6 kısa madde. Ton: {tone}. Hedef kitle: {audience}. Konu içeriği: {content}"
)


@dataclass
class Slide:
    """Tek slayt (yalnız içerik; başlık/içindekiler/kapanış builder'da)."""

    title: str
    bullets: list = field(default_factory=list)


@dataclass
class Outline:
    """Sunum planı."""

    title: str
    slides: list = field(default_factory=list)  # [Slide]


@dataclass
class PresentationResult:
    """Üretim sonucu — hangi yöntem, nerede, mesaj."""

    ok: bool
    method: str            # "pptx" | "canva" | "images"
    path: str = ""
    message: str = ""
    slide_count: int = 0


def normalize_outline(title: str, slides: list, num_slides: int) -> Outline:
    """Madde >6 ise slayt böl; başlıkları temizle (LLM ve şablon için ortak)."""
    out: list[Slide] = []
    for sl in slides:
        sl_title = str(sl.get("title", "")).strip() or "Konu"
        bullets = [str(b).strip() for b in (sl.get("bullets") or []) if str(b).strip()]
        if not bullets:
            bullets = [sl_title]
        for i in range(0, len(bullets), MAX_BULLETS):
            chunk = bullets[i:i + MAX_BULLETS]
            suffix = f" (devam {i // MAX_BULLETS + 1})" if i else ""
            out.append(Slide(title=sl_title + suffix, bullets=chunk))
    if not out:
        out = [Slide(title="Genel Bakış", bullets=["Sunum içeriği hazırlanamadı"])]
    # Hedef slayt sayısına yaklaştır (aşarsa kırp, eksikse şablon ekle)
    while len(out) > max(3, num_slides - 3):
        out.pop()
    return Outline(title=str(title).strip() or "Sunum", slides=out)


def template_outline(topic: str, num_slides: int, tone: str = "",
                     audience: str = "", content: str = "") -> Outline:
    """LLM yoksa şablon taslağı: içerik satırları + yapılandırıcı soru başlıkları."""
    target = max(2, num_slides - 3)
    bullets = [ln.strip() for ln in re.split(r"[\n•\-]+", content or "")
               if ln.strip()]
    slides: list[Slide] = []
    if bullets:
        for i in range(0, len(bullets), MAX_BULLETS):
            slides.append(Slide(title=f"{topic} — Bölüm {len(slides) + 1}",
                                bullets=bullets[i:i + MAX_BULLETS]))
    questions = [
        f"{topic} nedir?", "Neden önemli?", "Temel kavramlar",
        "Nasıl uygulanır?", "Örnekler ve vaka analizi",
        "Avantajlar ve zorluklar", "İstatistikler ve veriler",
        "Gelecek trendleri", "Sonuç ve öneriler",
    ]
    idx = 0
    while len(slides) < target:
        slides.append(Slide(title=questions[idx % len(questions)],
                            bullets=[f"{topic} bağlamında {questions[idx % len(questions)]}",
                                     "İlgili bulgular ve gözlemler",
                                     "Pratik çıkarımlar"]))
        idx += 1
    subtitle = " · ".join(x for x in (tone, audience) if x)
    return normalize_outline(topic if not subtitle else f"{topic} ({subtitle})",
                             [s.__dict__ for s in slides], num_slides)


def generate_outline(topic: str, num_slides: int = DEFAULT_SLIDES,
                     tone: str = "", audience: str = "",
                     content: str = "", llm_fn=None) -> Outline:
    """Konu/ton/hedef kitle/İçerikten outline üret (LLM varsa JSON, yoksa şablon)."""
    target = max(2, num_slides - 3)
    if llm_fn is not None:
        try:
            import json as _json
            instruction = _OUTLINE_INSTRUCTION.format(
                n=target, tone=tone or "profesyonel",
                audience=audience or "genel", content=(content or topic)[:2000])
            raw = llm_fn(topic, instruction, "")
            start, end = raw.find("{"), raw.rfind("}")
            if start >= 0 and end > start:
                data = _json.loads(raw[start:end + 1])
                outline = normalize_outline(
                    data.get("title") or topic,
                    data.get("slides") or [], num_slides)
                logger.info("[Present] LLM outline: %d slayt", len(outline.slides))
                return outline
        except Exception as exc:
            logger.warning("[Present] LLM outline başarısız, şablona düşülüyor: %s", exc)
    return template_outline(topic, num_slides, tone, audience, content)


def _build_pptx(outline: Outline, out_path: Path, topic: str) -> None:
    """python-pptx ile koyu temalı .pptx (başlık/içindekiler/içerik/kapanış)."""
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    BG = RGBColor(10, 15, 26)
    CYAN = RGBColor(0, 180, 255)
    LIGHT = RGBColor(220, 232, 245)
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    def _new_slide():
        s = prs.slides.add_slide(blank)
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = BG
        return s

    def _box(slide, left, top, width, height):
        return slide.shapes.add_textbox(Inches(left), Inches(top),
                                        Inches(width), Inches(height))

    # 1) Başlık slaytı
    s = _new_slide()
    tb = _box(s, 0.8, 2.4, 11.7, 1.6).text_frame
    tb.text = outline.title
    p = tb.paragraphs[0]
    p.font.size, p.font.bold, p.font.color.rgb = Pt(44), True, CYAN
    sub = _box(s, 0.8, 4.1, 11.7, 0.8).text_frame
    sub.text = time.strftime("%d.%m.%Y") + " · JARVIS ile üretildi"
    sub.paragraphs[0].font.size = Pt(16)
    sub.paragraphs[0].font.color.rgb = LIGHT

    # 2) İçindekiler
    s = _new_slide()
    tf = _box(s, 0.8, 0.5, 11.7, 6.5).text_frame
    tf.text = "İçindekiler"
    tf.paragraphs[0].font.size = Pt(30)
    tf.paragraphs[0].font.bold = True
    tf.paragraphs[0].font.color.rgb = CYAN
    for i, sl in enumerate(outline.slides, 1):
        para = tf.add_paragraph()
        para.text = f"{i}. {sl.title}"
        para.font.size = Pt(18)
        para.font.color.rgb = LIGHT

    # 3) İçerik slaytları (≤6 madde — normalize_outline garanti eder)
    for sl in outline.slides:
        s = _new_slide()
        tf = _box(s, 0.8, 0.5, 11.7, 6.5).text_frame
        tf.word_wrap = True
        tf.text = sl.title
        tf.paragraphs[0].font.size = Pt(28)
        tf.paragraphs[0].font.bold = True
        tf.paragraphs[0].font.color.rgb = CYAN
        for b in sl.bullets:
            para = tf.add_paragraph()
            para.text = f"• {b}"
            para.font.size = Pt(18)
            para.font.color.rgb = LIGHT

    # 4) Kapanış slaytı
    s = _new_slide()
    tf = _box(s, 0.8, 2.6, 11.7, 2.0).text_frame
    tf.text = "Teşekkürler"
    tf.paragraphs[0].font.size = Pt(44)
    tf.paragraphs[0].font.bold = True
    tf.paragraphs[0].font.color.rgb = CYAN
    p2 = tf.add_paragraph()
    p2.text = "Sorular ve Yorumlar"
    p2.font.size = Pt(20)
    p2.font.color.rgb = LIGHT
    prs.save(str(out_path))


def _build_canva(outline: Outline) -> PresentationResult | None:
    """Canva API — anahtar/connect yoksa None (fallback zinciri 3'e geçer)."""
    key = os.getenv("CANVA_API_KEY", "").strip()
    if not key:
        return None
    try:
        import requests
        resp = requests.post(
            "https://api.canva.com/v1/designs",
            headers={"Authorization": f"Bearer {key}"},
            json={"design_type": "presentation", "title": outline.title},
            timeout=15)
        resp.raise_for_status()
        url = resp.json().get("design", {}).get("url", "")
        return PresentationResult(True, "canva", url,
                                  f"Canva'da sunum oluşturuldu: {url}",
                                  len(outline.slides) + 3)
    except Exception as exc:
        logger.warning("[Present] Canva API başarısız (fallback'e geçilir): %s", exc)
        return None


def _build_images(outline: Outline, out_dir: Path) -> PresentationResult:
    """PNG slayt seti (Pillow) → klasör + zip — son çare, her zaman çalışır."""
    from PIL import Image, ImageDraw, ImageFont

    W, H = 1280, 720
    BG, CYAN, LIGHT = (10, 15, 26), (0, 180, 255), (220, 232, 245)

    def _font(size: int):
        for name in ("consolas.ttf", "arial.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    def _render(lines, name: str) -> Path:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        y = 60
        for text, size, color in lines:
            d.text((70, y), text, font=_font(size), fill=color)
            y += size + 18
        path = out_dir / name
        img.save(path, "PNG")
        return path

    out: list[Path] = []
    out.append(_render([(outline.title, 52, CYAN),
                        ("JARVIS ile üretildi", 22, LIGHT)], "s001_title.png"))
    toc = [("İçindekiler", 40, CYAN)]
    for i, sl in enumerate(outline.slides, 1):
        toc.append((f"{i}. {sl.title}", 22, LIGHT))
    out.append(_render(toc, "s002_toc.png"))
    for i, sl in enumerate(outline.slides, 1):
        lines = [(sl.title, 36, CYAN)]
        lines += [(f"• {b}", 22, LIGHT) for b in sl.bullets]
        out.append(_render(lines, f"s{i + 2:03d}.png"))
    out.append(_render([("Teşekkürler", 52, CYAN),
                        ("Sorular ve Yorumlar", 24, LIGHT)],
                       f"s{len(outline.slides) + 3:03d}_end.png"))
    import zipfile
    zip_path = out_dir / "slides.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in out:
            zf.write(p, p.name)
    return PresentationResult(
        True, "images", str(zip_path),
        f"PNG slayt seti üretildi ({len(outline.slides)} içerik slaytı + başlık/"
        f"içindekiler/kapanış → {len(out)} görsel, zip'li): {zip_path}",
        len(out))


def build_presentation(topic: str, num_slides: int | None = None,
                       tone: str = "", audience: str = "", content: str = "",
                       out_dir=None, llm_fn=None) -> PresentationResult:
    """Fallback zinciriyle sunum üret: pptx → canva → görseller."""
    num = max(3, min(30, int(num_slides) if num_slides else DEFAULT_SLIDES))
    outline = generate_outline(topic, num, tone, audience, content, llm_fn=llm_fn)
    slug = re.sub(r"[^\w\-]+", "_", topic, flags=re.UNICODE)[:40] or "sunum"
    base = Path(out_dir) if out_dir else OUT_ROOT / f"{slug}_{int(time.time())}"
    base.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []

    # 1) .pptx
    try:
        import pptx  # noqa: F401
        pptx_path = base / f"{slug}.pptx"
        _build_pptx(outline, pptx_path, topic)
        total = len(outline.slides) + 3
        return PresentationResult(
            True, "pptx", str(pptx_path),
            f"Sunum .pptx olarak üretildi: {pptx_path} ({total} slayt: başlık + "
            f"içindekiler + {len(outline.slides)} içerik + kapanış)", total)
    except ImportError:
        notes.append("python-pptx kurulu değil")
    except Exception as exc:
        logger.exception("[Present] pptx üretilemedi")
        notes.append(f"pptx hatası: {exc}")

    # 2) Canva (anahtar/bağlantı yoksa atlanır → kullanıcı bilgilendirilir)
    if os.getenv("CANVA_API_KEY", "").strip():
        result = _build_canva(outline)
        if result is not None:
            return result
        notes.append("Canva API başarısız")
    else:
        notes.append("Canva API anahtarı yok → 2. adım atlandı")

    # 3) PNG slayt seti
    try:
        result = _build_images(outline, base)
        result.message = f"{' / '.join(notes)} → FALLBACK. {result.message}"
        return result
    except Exception as exc:
        logger.exception("[Present] Görsel seti de üretilemedi")
        return PresentationResult(
            False, "none", "",
            f"Sunum üretilemedi: {' / '.join(notes)} / görsel hatası: {exc}", 0)
