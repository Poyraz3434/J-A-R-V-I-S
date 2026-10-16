"""AI haberleri — RSS beslemelerinden başlık çekme (stdlib XML ayrıştırıcı).

Besleme listesi JARVIS_NEWS_FEEDS ile değiştirilebilir (virgülle ayrılmış).
Varsayılan: iki küresel AI kaynağı + iki Türkçe teknoloji kaynağı.
"""
from __future__ import annotations

import datetime
import os
import re
import xml.etree.ElementTree as ET

import httpx

from .. import config

DEFAULT_FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://webrazzi.com/feed/",
    "https://trendyol-tech.github.io/feed.xml",
]

_TAG_STRIP = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return " ".join(_TAG_STRIP.sub("", text or "").split())


def _feeds() -> list[str]:
    raw = config.env("JARVIS_NEWS_FEEDS", "")
    feeds = [f.strip() for f in raw.split(",") if f.strip()]
    return feeds or DEFAULT_FEEDS


def _parse_feed(xml_text: str, source: str) -> list[dict]:
    items: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    # RSS 2.0
    for item in root.iter("item"):
        title = _clean(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if title:
            items.append(
                {"title": title, "link": link, "source": source, "published": pub}
            )
    # Atom
    ns = "{http://www.w3.org/2005/Atom}"
    for entry in root.iter(f"{ns}entry"):
        title = _clean(entry.findtext(f"{ns}title") or "")
        link_el = entry.find(f"{ns}link")
        link = link_el.get("href", "") if link_el is not None else ""
        updated = (entry.findtext(f"{ns}updated") or "").strip()
        if title:
            items.append(
                {"title": title, "link": link, "source": source, "published": updated}
            )
    return items


def fetch_ai_news(limit: int = 8, timeout: float = 12.0) -> dict:
    """Tüm beslemelerden en yeni başlıkları toplar (kaynak karışık, tarihli)."""
    limit = max(1, min(int(limit or 8), 20))
    all_items: list[dict] = []
    errors: list[str] = []

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            for url in _feeds():
                try:
                    resp = client.get(url)
                    if resp.status_code != 200:
                        errors.append(f"{url}: HTTP {resp.status_code}")
                        continue
                    all_items.extend(_parse_feed(resp.text, url))
                except httpx.HTTPError as exc:
                    errors.append(f"{url}: {exc}")
    except Exception as exc:  # beklenmedik — asla düşme
        return {"available": True, "items": [], "error": str(exc)}

    # Tarih bilinenleri öne al, sonra kaynağa göre grupla
    def dated(it: dict) -> datetime.datetime:
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)

    all_items.sort(key=dated, reverse=True)
    seen: set[str] = set()
    unique: list[dict] = []
    for it in all_items:
        key = it["title"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(it)

    result: dict = {"available": True, "items": unique[:limit], "count": len(unique)}
    if errors and not unique:
        result["error"] = "; ".join(errors[:3])
    return result


def available() -> bool:
    """Beslemeler varsayılan geldiği için her zaman kullanılabilir."""
    return True
