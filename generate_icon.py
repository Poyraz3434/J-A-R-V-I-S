"""JARVIS uygulama ikonu üretici (Pillow) — arc-reactor tarzı, çok formatlı.

Kullanım: python generate_icon.py
Çıktılar: JARVIS.ico (16..256 px, Windows) ve JARVIS.icns (macOS).
Tasarım değişirse bu scripti yeniden çalıştır; spec'e elle dokunma gerekmez.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).resolve().parent
S = 256  # ana boyut


def _draw_icon(size: int = S) -> Image.Image:
    """Koyu yuvarlatılmış kare + camgöbeği halka + parlak çekirdek."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = size / S

    # 1) Koyu yuvarlatılmış zemin (radius ≈ %22)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(56 * m),
                        fill=(10, 15, 26, 255))

    cx = cy = size / 2
    ring_r = 78 * m
    core_r = 26 * m

    # 2) Dış yumuşak parlama (konsantrik saydam halkalar)
    for i, alpha in ((24, 28), (16, 55), (9, 90)):
        r = ring_r + i * m
        d.ellipse([cx - r, cy - r, cx + r, cy + r],
                  outline=(0, 180, 255, alpha), width=int(10 * m))

    # 3) Ana camgöbeği halka
    d.ellipse([cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
              outline=(0, 196, 255, 255), width=int(13 * m))

    # 4) İç detay: ince ikinci halka
    r2 = ring_r - 26 * m
    d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2],
              outline=(120, 230, 255, 200), width=int(5 * m))

    # 5) Çekirdek: kademeli parlak daireler (glow hissi)
    for r, color in ((core_r + 14 * m, (0, 180, 255, 70)),
                     (core_r + 6 * m, (140, 240, 255, 150)),
                     (core_r, (235, 252, 255, 255))):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    # 6) Tepe çıkıntısı (reaktör pimi)
    d.rounded_rectangle([cx - 14 * m, 6 * m, cx + 14 * m, 30 * m],
                        radius=int(6 * m), fill=(0, 140, 210, 255))
    return img


def main() -> None:
    icon = _draw_icon()
    ico_path = OUT_DIR / "JARVIS.ico"
    icon.save(ico_path, format="ICO",
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                     (64, 64), (128, 128), (256, 256)])
    icns_path = OUT_DIR / "JARVIS.icns"
    try:
        icon.save(icns_path, format="ICNS")
        icns_note = f", {icns_path.name}"
    except Exception as exc:  # Pillow ICNS desteği yoksa sadece .ico
        icns_note = f" (icns atlandı: {exc})"
    print(f"OK: {ico_path.name} ({ico_path.stat().st_size} bytes)"
          f"{icns_note}")


if __name__ == "__main__":
    main()
