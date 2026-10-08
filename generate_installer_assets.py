"""JARVIS kurucu (Inno Setup) görselleri üretici (Pillow).

Çıktılar (24-bit BMP):
  installer_wizard.bmp  —640×149 sihirbaz karşı görseli
  installer_small.bmp   — 55×58 sol üst marka görseli
Kullanım: python generate_installer_assets.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent
BG = (10, 15, 26)
CYAN = (0, 180, 255)
LIGHT = (200, 216, 240)


def _font(size: int):
    for name in ("consolas.ttf", "arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wizard_image() -> Image.Image:
    """640×149 — koyu zemin, camgöbeği kenar çizgisi, başlık + alt başlık."""
    w, h = 640, 149
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    # Sol kenar vurgu şeridi
    d.rectangle([0, 0, 6, h], fill=CYAN)
    # İnce alt çizgi
    d.line([(24, h - 18), (w - 24, h - 18)], fill=(30, 60, 90), width=1)
    # Mini reaktör simgesi
    cx, cy = 60, h // 2
    d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], outline=CYAN, width=5)
    d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=(235, 252, 255))
    # Metinler
    d.text((110, 38), "J.A.R.V.I.S.", font=_font(38), fill=CYAN)
    d.text((112, 88), "Yapay Zeka Asistani — Kurulum Sihirbazi",
           font=_font(15), fill=LIGHT)
    return img


def _small_image() -> Image.Image:
    """55×58 — sol üstte kompakt logo."""
    w, h = 55, 58
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    d.ellipse([cx - 17, cy - 17, cx + 17, cy + 17], outline=CYAN, width=4)
    d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=(235, 252, 255))
    return img


def main() -> None:
    big = OUT_DIR / "installer_wizard.bmp"
    small = OUT_DIR / "installer_small.bmp"
    _wizard_image().save(big, format="BMP")            # Pillow24-bit BMP yazar
    _small_image().save(small, format="BMP")
    print(f"OK: {big.name} ({big.stat().st_size} bytes), "
          f"{small.name} ({small.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
