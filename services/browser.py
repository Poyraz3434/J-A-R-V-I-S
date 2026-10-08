"""Safe browser and local diagnostics actions for Jarvis."""
from __future__ import annotations

import os
import platform
import webbrowser
from pathlib import Path
from urllib.parse import quote, urlparse

ALLOWED_HOSTS = {"www.google.com", "www.youtube.com", "youtube.com"}


def _open_allowed(url: str) -> str:
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS
            or parsed.username or parsed.password or parsed.port not in {None, 443}):
        return "Bu adres güvenlik politikası nedeniyle açılamadı."
    try:
        webbrowser.open_new_tab(url)
        return f"Tarayıcıda açıldı: {url}"
    except Exception as exc:
        return f"Tarayıcı açılamadı: {exc}"


def open_google(query: str) -> str:
    query = " ".join((query or "").split())[:240]
    if not query:
        return _open_allowed("https://www.google.com")
    return _open_allowed(f"https://www.google.com/search?q={quote(query)}")


def open_youtube(query: str) -> str:
    query = " ".join((query or "").split())[:240]
    if not query:
        return _open_allowed("https://www.youtube.com")
    return _open_allowed(f"https://www.youtube.com/results?search_query={quote(query)}")


def system_summary() -> str:
    return (
        f"Sistem: {platform.system()} {platform.release()}\n"
        f"Makine: {platform.machine()}\n"
        f"Python: {platform.python_version()}\n"
        f"Kullanıcı klasörü: {Path.home()}\n"
        "Not: Değişiklik yapmadan önce açık onay gerekir."
    )


def find_local_item(query: str, max_results: int = 10) -> str:
    """Search only under the user's home directory, without opening or changing files."""
    needle = " ".join((query or "").lower().split())[:120]
    if len(needle) < 2:
        return "Arama için en az iki karakter belirtin."
    results: list[str] = []
    excluded = {"appdata", ".git", "node_modules", "__pycache__"}
    try:
        for root, dirs, files in os.walk(Path.home()):
            dirs[:] = [item for item in dirs if item.lower() not in excluded]
            for name in [*dirs, *files]:
                if needle in name.lower():
                    results.append(str(Path(root) / name))
                    if len(results) >= max_results:
                        break
            if len(results) >= max_results:
                break
    except OSError as exc:
        return f"Yerel arama yapılamadı: {exc}"
    if not results:
        return f"'{needle}' için kullanıcı klasöründe sonuç bulunamadı."
    return "Bulunanlar:\n" + "\n".join(f"- {path}" for path in results)
