"""Bounded browser automation for public HTTPS pages.

Login, payment, password, download and destructive actions are intentionally
not automated here. Page interaction is opt-in and confirmation-gated by the
caller.
"""
from __future__ import annotations

import ipaddress
import os
import socket
import webbrowser
from urllib.parse import urlparse

_DEFAULT_AUTOMATION_HOSTS = {
    "yemeksepeti.com", "www.yemeksepeti.com",
    "sahibinden.com", "www.sahibinden.com",
}
_ALLOWED_AUTOMATION_HOSTS = {
    item.strip().lower()
    for item in os.getenv("JARVIS_WEB_AUTOMATION_HOSTS", "").split(",")
    if item.strip()
} or _DEFAULT_AUTOMATION_HOSTS
_MARKETPLACE_PLAYWRIGHT = None
_MARKETPLACE_BROWSER = None
_PAGE_TIMEOUT_MS = 60_000
_ELEMENT_TIMEOUT_MS = 30_000


def _validate_url(url: str, require_allowlist: bool = False) -> str | None:
    parsed = urlparse((url or "").strip())
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.port not in {None, 443}):
        return "Yalnızca kimlik bilgisi içermeyen HTTPS adresleri açılabilir."
    if require_allowlist and parsed.hostname.lower() not in _ALLOWED_AUTOMATION_HOSTS:
        return "Bu domain web otomasyonu için allowlist içinde değil."
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return "Yerel veya özel ağ adreslerine tarayıcı otomasyonu engellendi."
    except (OSError, ValueError):
        return "Web adresi doğrulanamadı."
    return None


def open_url(url: str) -> str:
    error = _validate_url(url)
    if error:
        return error
    try:
        webbrowser.open_new_tab(url.strip())
        return f"Web sayfası açıldı: {url.strip()}"
    except Exception as exc:
        return f"Web sayfası açılamadı: {exc}"


def interact(url: str, action: str, target: str, value: str = "") -> str:
    error = _validate_url(url, require_allowlist=True)
    if error:
        return error
    if action not in {"click", "fill"}:
        return "Yalnızca tıklama ve alan doldurma destekleniyor."
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "Web etkileşimi için playwright kurun: pip install playwright && playwright install chromium"

    browser = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            page = browser.new_page()
            def guard_route(route):
                request_url = route.request.url
                if (urlparse(request_url).scheme in {"http", "https"}
                    and _validate_url(request_url, require_allowlist=True)):
                    route.abort()
                    return
                route.continue_()

            page.route("**/*", guard_route)
            page.goto(
                url.strip(),
                wait_until="domcontentloaded",
                timeout=_PAGE_TIMEOUT_MS,
            )
            if _validate_url(page.url, require_allowlist=True):
                return "Yönlendirme güvenlik politikası nedeniyle engellendi."
            locator = page.get_by_text(target, exact=False).first if action == "click" else page.get_by_label(target, exact=False).first
            if action == "click":
                locator.click(timeout=_ELEMENT_TIMEOUT_MS)
                result = f"'{target}' öğesine tıklandı."
            else:
                locator.fill(value[:500], timeout=_ELEMENT_TIMEOUT_MS)
                result = f"'{target}' alanı dolduruldu."
            return result
    except Exception as exc:
        return f"Web etkileşimi başarısız: {exc}"
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass


def marketplace_search(site: str, query: str) -> str:
    """Search approved marketplace sites and leave final decisions to the user."""
    global _MARKETPLACE_PLAYWRIGHT, _MARKETPLACE_BROWSER
    site_key = " ".join((site or "").lower().split())
    query = " ".join((query or "").split())[:240]
    if not query:
        return "Arama için ne istediğinizi belirtin."
    if site_key in {"yemeksepeti", "yemek sepeti"}:
        host = "www.yemeksepeti.com"
        label = "Yemeksepeti"
        selectors = (
            "input[type='search']", "input[placeholder*='Ara']",
            "input[aria-label*='Ara']",
        )
    elif site_key in {"sahibinden", "sahibinden.com"}:
        host = "www.sahibinden.com"
        label = "Sahibinden"
        selectors = (
            "input[type='search']", "input[placeholder*='Ara']",
            "input[aria-label*='Ara']",
        )
    else:
        return "Bu site için güvenli marketplace adapter'ı bulunmuyor."

    url = f"https://{host}/"
    error = _validate_url(url, require_allowlist=True)
    if error:
        return error
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "Marketplace araması için playwright ve Chromium kurulumu gerekli."

    close_marketplace_browser()
    try:
        _MARKETPLACE_PLAYWRIGHT = sync_playwright().start()
        _MARKETPLACE_BROWSER = _MARKETPLACE_PLAYWRIGHT.chromium.launch(headless=False)
        page = _MARKETPLACE_BROWSER.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=_PAGE_TIMEOUT_MS)
        if _validate_url(page.url, require_allowlist=True):
            return "Marketplace yönlendirmesi güvenlik politikası nedeniyle engellendi."
        body_text = page.locator("body").inner_text(timeout=_ELEMENT_TIMEOUT_MS).strip()
        blocked_markers = (
            "olağandışı bir durum", "şu anda talebinizi gerçekleştiremiyoruz",
            "unusual traffic", "access denied", "captcha",
        )
        if any(marker in body_text.lower() for marker in blocked_markers):
            close_marketplace_browser()
            webbrowser.open_new_tab(url)
            return (
                "Robot doğrulama algılandı. Doğrulamayı normal tarayıcıda tamamlayın; "
                "çözüldükten sonra aynı komutu tekrar gönderdiğinizde ATLAS yeniden başlayacaktır."
            )
        search_box = None
        for selector in selectors:
            candidate = page.locator(selector).first
            if candidate.count():
                search_box = candidate
                break
        if search_box is None:
            return f"{label} açık bırakıldı ancak arama kutusu bulunamadı; tarayıcıda aramayı tamamlayın."
        search_box.fill(query)
        search_box.press("Enter")
        page.wait_for_load_state("domcontentloaded", timeout=_PAGE_TIMEOUT_MS)
        if _validate_url(page.url, require_allowlist=True):
            return "Arama yönlendirmesi güvenlik politikası nedeniyle engellendi."
        visible_text = page.locator("body").inner_text(
            timeout=_ELEMENT_TIMEOUT_MS
        ).strip()[:4000]
        return (
            f"{label} üzerinde '{query}' araması tamamlandı.\n\n"
            f"{visible_text or 'Sonuç metni okunamadı; açık tarayıcıda inceleyin.'}\n\n"
            "Sepet, sipariş, ödeme ve satıcı iletişimi ATLAS tarafından otomatik yapılmaz."
        )
    except Exception as exc:
        close_marketplace_browser()
        return f"{label} araması başlatılamadı: {exc}"


def close_marketplace_browser() -> None:
    global _MARKETPLACE_PLAYWRIGHT, _MARKETPLACE_BROWSER
    if _MARKETPLACE_BROWSER is not None:
        try:
            _MARKETPLACE_BROWSER.close()
        except Exception:
            pass
        _MARKETPLACE_BROWSER = None
    if _MARKETPLACE_PLAYWRIGHT is not None:
        try:
            _MARKETPLACE_PLAYWRIGHT.stop()
        except Exception:
            pass
        _MARKETPLACE_PLAYWRIGHT = None
