import threading
import time
from urllib.parse import quote, urlparse

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    requests = None
    HTTPAdapter = None
    Retry = None

from config import CITY, OWM_API_KEY
from logger_setup import logger

HTTP_CONNECT_TIMEOUT_SECONDS = 10
HTTP_READ_TIMEOUT_SECONDS = 90
DEFAULT_HTTP_TIMEOUT = (
    HTTP_CONNECT_TIMEOUT_SECONDS,
    HTTP_READ_TIMEOUT_SECONDS,
)
HTTP_RETRY_TOTAL = 2


def _create_http_session():
    if requests is None:
        return None
    session = requests.Session()
    if HTTPAdapter is not None and Retry is not None:
        retry_policy = Retry(
            total=HTTP_RETRY_TOTAL,
            connect=HTTP_RETRY_TOTAL,
            read=HTTP_RETRY_TOTAL,
            status=HTTP_RETRY_TOTAL,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "HEAD"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry_policy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
    return session


HTTP_SESSION = _create_http_session()
REQUEST_CACHE = {}
REQUEST_CACHE_LOCK = threading.Lock()
REQUEST_CACHE_MAX = 256
REQUEST_CACHE_STALE_TTL = 1800
REQUEST_CACHE_KEY_LOCKS = {}
_ALLOWED_HOSTS = {"api.openweathermap.org", "api.exchangerate-api.com", "api.frankfurter.app"}


def _is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and parsed.netloc in _ALLOWED_HOSTS


def get_cached_json(
    url: str,
    timeout: int | tuple[int, int] = DEFAULT_HTTP_TIMEOUT,
    cache_ttl: int = 300,
    headers: dict | None = None,
    stale_ttl: int = REQUEST_CACHE_STALE_TTL,
):
    if HTTP_SESSION is None:
        return None
    if not _is_safe_url(url):
        return None
    key = (url, tuple(sorted((headers or {}).items())), timeout)
    with REQUEST_CACHE_LOCK:
        lock_entry = REQUEST_CACHE_KEY_LOCKS.get(key)
        if lock_entry is None:
            key_lock = threading.Lock()
            REQUEST_CACHE_KEY_LOCKS[key] = (key_lock, 1)
        else:
            key_lock, users = lock_entry
            REQUEST_CACHE_KEY_LOCKS[key] = (key_lock, users + 1)

    try:
        with key_lock:
            now = time.time()
            with REQUEST_CACHE_LOCK:
                cached = REQUEST_CACHE.get(key)
            if cached and (now - cached["ts"]) < cache_ttl:
                return cached["data"]

            try:
                response = HTTP_SESSION.get(url, timeout=timeout, headers=headers)
                response.raise_for_status()
                payload = response.json()
                with REQUEST_CACHE_LOCK:
                    if len(REQUEST_CACHE) >= REQUEST_CACHE_MAX and key not in REQUEST_CACHE:
                        REQUEST_CACHE.pop(next(iter(REQUEST_CACHE)))
                    REQUEST_CACHE[key] = {"ts": time.time(), "data": payload}
                return payload
            except Exception as exc:
                logger.warning(
                    "Cached JSON request to %s failed (%s)",
                    urlparse(url).netloc,
                    type(exc).__name__,
                )
                if cached and (now - cached["ts"]) <= cache_ttl + stale_ttl:
                    return cached["data"]
                return None
    finally:
        with REQUEST_CACHE_LOCK:
            current_lock, users = REQUEST_CACHE_KEY_LOCKS[key]
            if users == 1:
                del REQUEST_CACHE_KEY_LOCKS[key]
            else:
                REQUEST_CACHE_KEY_LOCKS[key] = (current_lock, users - 1)


def get_weather() -> dict:
    if not OWM_API_KEY:
        return {"temp": "?", "desc": "API yok", "humidity": "?", "rain_prob": "Bilinmiyor"}
    if not CITY.strip():
        return {"temp": "?", "desc": "JARVIS_CITY ayarlanmamış", "humidity": "?", "rain_prob": "?"}
    try:
        city_query = quote(CITY.strip())
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={city_query}&appid={quote(OWM_API_KEY)}&units=metric&lang=tr"
        )
        data = get_cached_json(url, timeout=DEFAULT_HTTP_TIMEOUT, cache_ttl=180)
        if not data:
            return {"temp": "?", "desc": "İstek alınamadı", "humidity": "?", "rain_prob": "?"}
        rain = data.get("rain", {}).get("1h", 0)
        return {
            "temp": round(data["main"]["temp"]),
            "desc": data["weather"][0]["description"],
            "humidity": data["main"]["humidity"],
            "rain_prob": f"%{min(int(rain * 100), 100)}" if rain else "Düşük",
            "feels": round(data["main"]["feels_like"]),
        }
    except Exception as exc:
        if requests and isinstance(exc, requests.exceptions.Timeout):
            return {"temp": "?", "desc": "Zaman aşımı", "humidity": "?", "rain_prob": "?"}
        if requests and isinstance(exc, requests.exceptions.HTTPError):
            status_code = getattr(exc.response, "status_code", "?")
            return {"temp": "?", "desc": f"HTTP {status_code}", "humidity": "?", "rain_prob": "?"}
        logger.exception("Weather fetch failed")
        return {"temp": "?", "desc": "Alınamadı", "humidity": "?", "rain_prob": "?"}


# keep currency helper in main file for now; all network requests are centralized here.
__all__ = [
    "DEFAULT_HTTP_TIMEOUT",
    "HTTP_SESSION",
    "HTTP_READ_TIMEOUT_SECONDS",
    "REQUEST_CACHE",
    "get_cached_json",
    "get_weather",
]
