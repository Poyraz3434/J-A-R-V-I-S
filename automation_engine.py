"""ATLAS automation state machine — Selenium tabanlı, reklam filtreli, yeniden deneme destekli."""
from __future__ import annotations

import difflib
import threading
import time
import urllib.parse
from enum import Enum
from urllib.parse import urlparse

from PySide6.QtCore import QObject, Signal

from logger_setup import logger
from screen_watcher import ScreenWatcher

# ── Site → URL eşlemesi ─────────────────────────────────────────────────────
SITE_URLS: dict[str, str] = {
    "youtube.com":      "https://www.youtube.com/results?search_query={query}",
    "youtube":          "https://www.youtube.com/results?search_query={query}",
    "google.com":       "https://www.google.com/search?q={query}",
    "google":           "https://www.google.com/search?q={query}",
    "sahibinden.com":   "https://www.sahibinden.com/arama?query={query}",
    "sahibinden":       "https://www.sahibinden.com/arama?query={query}",
    "yemeksepeti.com":  "https://www.yemeksepeti.com/search?query={query}",
    "yemeksepeti":      "https://www.yemeksepeti.com/search?query={query}",
}

# YouTube reklam element seçicileri
YT_AD_SELECTORS = [
    "ytd-promoted-video-renderer",
    "ytd-display-ad-renderer",
    "ytd-promoted-sparkles-web-renderer",
    "ytd-movie-renderer",   # ücretli filmler
]
YT_VIDEO_SELECTOR = "ytd-video-renderer"
YT_TITLE_SELECTOR = "#video-title"


class AutomationState(str, Enum):
    RUNNING = "RUNNING"
    PAUSED_BY_USER = "PAUSED_BY_USER"
    PAUSED_BY_VERIFICATION = "PAUSED_BY_VERIFICATION"
    STOPPED = "STOPPED"


def _similarity(a: str, b: str) -> float:
    """İki metin arasındaki benzerlik oranı (0.0–1.0)."""
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


class AutomationEngine(QObject):
    """Successful tasks leave the browser visible; stop/app shutdown closes it."""
    state_changed = Signal(str, str)
    message       = Signal(str)
    finished      = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state        = AutomationState.STOPPED
        self._state_lock   = threading.Lock()
        self._resume_event = threading.Event()
        self._resume_event.set()
        self._stop_event   = threading.Event()
        self._thread: threading.Thread | None = None
        self._watcher      = ScreenWatcher()
        self._failures     = 0
        self._driver       = None   # Selenium WebDriver (her oturum için yeniden oluşturulur)
        self.tried_results: list[str] = []  # denenen video URL'leri

    # ── Durum ────────────────────────────────────────────────────────────────
    @property
    def state(self) -> AutomationState:
        with self._state_lock:
            return self._state

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _set_state(self, state: AutomationState, detail: str = ""):
        with self._state_lock:
            self._state = state
        self.state_changed.emit(state.value, detail)

    # ── Genel kontrol ────────────────────────────────────────────────────────
    def pause(self):
        if self.state == AutomationState.RUNNING:
            self._resume_event.clear()
            self._set_state(AutomationState.PAUSED_BY_USER, "Kullanıcı durdurdu.")

    def resume(self):
        if self.state in {AutomationState.PAUSED_BY_USER, AutomationState.PAUSED_BY_VERIFICATION}:
            self._resume_event.set()
            self._set_state(AutomationState.RUNNING, "Otomasyon devam ediyor.")

    def stop(self):
        self._stop_event.set()
        self._resume_event.set()
        self._set_state(AutomationState.STOPPED, "Otomasyon sonlandırıldı.")
        # WebDriver is not thread-safe: an active automation thread owns cleanup.
        if not self.is_running:
            self._quit_driver()

    # ── Genel başlatıcı (öncekini durdurur) ─────────────────────────────────
    def _start_thread(self, target, *args) -> bool:
        if self._thread and self._thread.is_alive():
            self.message.emit("ATLAS zaten bir otomasyon çalıştırıyor.")
            return False
        self._stop_event.clear()
        self._resume_event.set()
        self._failures     = 0
        self.tried_results = []
        self._thread = threading.Thread(target=target, args=args, daemon=True)
        self._thread.start()
        return True

    # ── Genel API ────────────────────────────────────────────────────────────
    def start_youtube(self, query: str) -> bool:
        return self.open_youtube_and_search(query)

    def open_youtube_and_search(self, query: str) -> bool:
        return self._start_thread(self._run_youtube, query)

    def open_url(self, url: str) -> bool:
        return self._start_thread(self._run_open_url, url)

    def search_on_site(self, site: str, query: str) -> bool:
        return self._start_thread(self._run_site_search, site, query)

    # ── Checkpoint & adım yönetimi ───────────────────────────────────────────
    def _checkpoint(self, detail: str) -> bool:
        self.message.emit(detail)
        while not self._stop_event.is_set():
            if self._watcher.verification_detected():
                self._resume_event.clear()
                self._set_state(
                    AutomationState.PAUSED_BY_VERIFICATION,
                    "Doğrulama bekleniyor; doğrulamayı kendiniz tamamlayın.",
                )
                self.message.emit("Robot doğrulama algılandı. Doğrulamayı kendiniz tamamlayın.")
                while not self._stop_event.is_set() and self._watcher.verification_detected():
                    time.sleep(1.5)
                if self._stop_event.is_set():
                    return False
                self._resume_event.set()
                self._set_state(AutomationState.RUNNING, "Doğrulama temizlendi, devam ediliyor.")
            if self._resume_event.wait(0.2):
                return not self._stop_event.is_set()
        return False

    def _run_step(self, step, description: str) -> bool:
        failures = 0
        while failures < 3 and not self._stop_event.is_set():
            if not self._checkpoint(description):
                return False
            try:
                step()
                self._failures = 0
                return self._checkpoint(f"Tamamlandı: {description}")
            except Exception as exc:
                failures += 1
                self._failures += 1
                self.message.emit(f"ATLAS adımı başarısız ({failures}/3): {exc}")
        self._resume_event.clear()
        self._set_state(AutomationState.PAUSED_BY_USER, "Üç ardışık hata; Devam Et ile yeniden denenecek.")
        return self._checkpoint(f"Beklemede: {description}")

    # ── Selenium yardımcıları ────────────────────────────────────────────────
    def _get_driver(self):
        """Mevcut driver'ı döndür ya da yenisini oluştur."""
        if self._driver:
            try:
                _ = self._driver.window_handles  # canlı mı kontrol et
                return self._driver
            except Exception:
                self._driver = None

        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager

        opts = Options()
        # Görünür tarayıcı (headless değil)
        opts.add_argument("--start-maximized")
        opts.add_argument("--disable-notifications")
        opts.add_argument("--disable-infobars")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)

        service = Service(ChromeDriverManager().install())
        self._driver = webdriver.Chrome(service=service, options=opts)
        self._driver.set_page_load_timeout(90)
        self._driver.set_script_timeout(60)
        return self._driver

    def _quit_driver(self):
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                logger.exception("ATLAS WebDriver kapatılırken hata oluştu")
            self._driver = None

    # ── YouTube otomasyonu ───────────────────────────────────────────────────
    def _run_youtube(self, query: str):
        self._set_state(AutomationState.RUNNING, "YouTube otomasyonu başlıyor.")
        try:
            clean_query  = " ".join(query.split())[:200]
            search_url   = (
                "https://www.youtube.com/results?search_query="
                + urllib.parse.quote(clean_query)
            )
            driver = self._get_driver()

            if not self._run_step(
                lambda: driver.get(search_url),
                f"YouTube'da aranıyor: {clean_query}",
            ):
                return

            if not self._run_step(
                lambda: time.sleep(4),
                "Sayfa yükleniyor...",
            ):
                return

            # Reklam filtreli video listesi çek
            if not self._youtube_click_best(driver, clean_query):
                self.message.emit("Uygun video bulunamadı, arama yeniden yapılıyor...")
                retry_query = clean_query + " official"
                retry_url   = (
                    "https://www.youtube.com/results?search_query="
                    + urllib.parse.quote(retry_query)
                )
                if self._run_step(lambda: driver.get(retry_url), f"Yeniden aranıyor: {retry_query}"):
                    if not self._run_step(
                        lambda: time.sleep(4),
                        "Yeniden arama sonuçları yükleniyor...",
                    ):
                        return
                    if not self._youtube_click_best(driver, clean_query):
                        self.message.emit(
                            "Video oynatılamadı. YouTube doğrulaması veya oynatma "
                            "butonuna elle basmanız gerekebilir."
                        )

        except Exception as exc:
            self.message.emit(f"YouTube otomasyonu hatası: {exc}")
        finally:
            if self._stop_event.is_set():
                self._quit_driver()
            self._set_state(AutomationState.STOPPED, "Otomasyon tamamlandı.")
            self.finished.emit()

    def _youtube_click_best(self, driver, query: str) -> bool:
        """
        Open the best non-ad YouTube result and confirm actual video playback.
        """
        from selenium.webdriver.common.by import By

        try:
            videos = driver.find_elements(By.CSS_SELECTOR, YT_VIDEO_SELECTOR)
            self.message.emit(f"{len(videos)} video sonucu bulundu, reklam taranıyor...")

            candidates = []
            for vid in videos:
                outer_html = vid.get_attribute("outerHTML") or ""
                # Reklam kontrolü — birden fazla yöntemle
                if any(sel.replace("ytd-", "").replace("-renderer", "") in outer_html.lower()
                       for sel in YT_AD_SELECTORS):
                    self.message.emit("Reklam tespit edildi, atlanıyor.")
                    continue
                if "reklam" in (vid.text or "").lower() or '"ad"' in outer_html.lower():
                    self.message.emit("Reklam içeriği atlandı.")
                    continue

                # Başlık çek
                try:
                    title_el = vid.find_element(By.CSS_SELECTOR, YT_TITLE_SELECTOR)
                    title    = (title_el.text or title_el.get_attribute("title") or "").strip()
                    href     = title_el.get_attribute("href") or ""
                except Exception:
                    continue

                if href in self.tried_results:
                    continue  # daha önce denendi

                score = _similarity(query, title)
                candidates.append((score, title, href, vid))

            if not candidates:
                self.message.emit("Hiç uygun video adayı bulunamadı.")
                return False

            # En yüksek skora göre sırala
            candidates.sort(key=lambda x: x[0], reverse=True)

            for score, title, href, vid_el in candidates:
                self.message.emit(f"Video adayı: '{title}' (benzerlik: %{int(score*100)})")
                if score < 0.25:
                    self.message.emit(f"Benzerlik çok düşük (%{int(score*100)}), atlanıyor.")
                    continue

                # Tıkla
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", vid_el)
                    video_url = urllib.parse.urljoin(driver.current_url, href)
                    parsed_url = urlparse(video_url)
                    if (
                        parsed_url.scheme != "https"
                        or parsed_url.hostname not in {"www.youtube.com", "youtube.com", "youtu.be"}
                        or not (
                            parsed_url.path.startswith("/watch")
                            or parsed_url.hostname == "youtu.be"
                        )
                    ):
                        self.message.emit("Güvenli YouTube video bağlantısı alınamadı; sonuç atlandı.")
                        continue

                    self.message.emit(f"Video açılıyor: {title}")
                    if not self._run_step(
                        lambda url=video_url: driver.get(url),
                        f"YouTube videosu açılıyor: {title}",
                    ):
                        return False
                    self.tried_results.append(video_url)

                    if self._wait_for_video_playback(driver):
                        self.message.emit(f"✓ Video oynatımı doğrulandı: {title}")
                        return True
                    self.message.emit(
                        f"Video sayfası açıldı ancak oynatma başlamadı: {title}. "
                        "Oynatma engellenmiş veya kullanıcı etkileşimi bekleniyor olabilir."
                    )
                    return False
                except Exception as exc:
                    self.message.emit(f"Tıklama hatası: {exc}")
                    continue

            return False

        except Exception as exc:
            self.message.emit(f"Video listesi okunamadı: {exc}")
            return False

    def _wait_for_video_playback(self, driver, timeout: float = 12.0) -> bool:
        """Wait for YouTube's video element to report active playback."""
        deadline = time.monotonic() + timeout
        play_attempted = False
        playback_script = (
            "const v=document.querySelector('video');"
            "return !!(v && !v.paused && !v.ended && v.readyState >= 2 && v.currentTime > 0);"
        )
        while not self._stop_event.is_set():
            try:
                if driver.execute_script(playback_script):
                    return True
            except Exception as exc:
                logger.warning("YouTube playback state check failed: %s", type(exc).__name__)

            if not play_attempted:
                play_attempted = True
                try:
                    buttons = driver.find_elements(
                        "css selector",
                        ".ytp-large-play-button, .ytp-play-button",
                    )
                    for button in buttons:
                        if button.is_displayed() and button.is_enabled():
                            button.click()
                            break
                except Exception as exc:
                    logger.warning("YouTube play button click failed: %s", type(exc).__name__)

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.5, remaining))
        return False

    # ── Genel URL aç ────────────────────────────────────────────────────────
    def _run_open_url(self, url: str):
        self._set_state(AutomationState.RUNNING, f"URL açılıyor: {url}")
        try:
            from services.web_automation import _validate_url

            validation_error = _validate_url(url)
            if validation_error:
                self.message.emit(validation_error)
                return
            driver = self._get_driver()
            if self._run_step(lambda: driver.get(url), f"Tarayıcıda açılıyor: {url}"):
                self.message.emit(f"✓ URL açıldı: {url}")
        except Exception as exc:
            self.message.emit(f"URL açılamadı: {exc}")
        finally:
            if self._stop_event.is_set():
                self._quit_driver()
            self._set_state(AutomationState.STOPPED, "Otomasyon tamamlandı.")
            self.finished.emit()

    # ── Site üzerinde arama ─────────────────────────────────────────────────
    def _run_site_search(self, site: str, query: str):
        self._set_state(AutomationState.RUNNING, f"{site} üzerinde aranıyor: {query}")
        try:
            url_template = SITE_URLS.get(site.lower())
            if not url_template:
                self.message.emit(f"Bilinmeyen site: {site}. Desteklenen: {list(SITE_URLS.keys())}")
                return

            encoded = urllib.parse.quote(query)
            url     = url_template.format(query=encoded)
            driver  = self._get_driver()

            if not self._run_step(lambda: driver.get(url), f"{site} açılıyor..."):
                return

            if not self._run_step(lambda: time.sleep(3), "Sayfa yükleniyor..."):
                return

            # YouTube için reklam filtreli tıklama
            if "youtube" in site.lower():
                if not self._youtube_click_best(driver, query):
                    self.message.emit(
                        "YouTube sonucu açıldı ancak video oynatımı doğrulanamadı."
                    )
            else:
                self.message.emit(f"✓ {site} arama sonuçları açıldı: {query}")

        except Exception as exc:
            self.message.emit(f"Site arama hatası: {exc}")
        finally:
            if self._stop_event.is_set():
                self._quit_driver()
            self._set_state(AutomationState.STOPPED, "Otomasyon tamamlandı.")
            self.finished.emit()
