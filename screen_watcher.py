"""Screen capture and manual verification detection for ATLAS automation."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


VERIFICATION_KEYWORDS = (
    "doğrulama", "robot değilim", "captcha", "i am not a robot",
    "i'm not a robot", "verify you are human", "verify you are a human",
    "olağandışı bir durum", "unusual traffic", "access denied",
)


@dataclass(frozen=True)
class ScreenMatch:
    text: str
    left: int
    top: int
    width: int
    height: int


class ScreenWatcher:
    """Captures the screen and detects verification pages without solving them."""

    def __init__(self, keywords: Iterable[str] = VERIFICATION_KEYWORDS):
        self.keywords = tuple(keyword.lower() for keyword in keywords)

    def _image(self):
        import mss
        with mss.mss() as screen:
            monitor = screen.monitors[0]
            return screen.grab(monitor)

    def read_text(self) -> str:
        try:
            import pytesseract
            from PIL import Image
            image = self._image()
            return pytesseract.image_to_string(Image.frombytes("RGB", image.size, image.rgb), lang="tur+eng")
        except Exception:
            return ""

    def verification_detected(self, text: str | None = None) -> bool:
        content = (self.read_text() if text is None else text).lower()
        normalized = re.sub(r"\s+", " ", content)
        return any(keyword in normalized for keyword in self.keywords)

    def find_text(self, query: str) -> ScreenMatch | None:
        """Return an OCR box for a visible query fragment, if available."""
        try:
            import pytesseract
            from PIL import Image
            image = self._image()
            pil_image = Image.frombytes("RGB", image.size, image.rgb)
            data = pytesseract.image_to_data(
                pil_image, lang="tur+eng", output_type=pytesseract.Output.DICT
            )
            query_words = {word.lower() for word in query.split() if len(word) > 2}
            best: ScreenMatch | None = None
            for index, raw in enumerate(data.get("text", [])):
                word = raw.strip()
                if not word or word.lower() not in query_words:
                    continue
                match = ScreenMatch(
                    word,
                    int(data["left"][index]), int(data["top"][index]),
                    int(data["width"][index]), int(data["height"][index]),
                )
                if match.top < 120:
                    continue
                if best is None:
                    best = match
            return best
        except Exception:
            return None
