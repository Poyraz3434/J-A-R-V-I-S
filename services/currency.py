"""Currency lookup, conversion, and presentation helpers."""
from __future__ import annotations

import datetime
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from logger_setup import logger
from services.network import DEFAULT_HTTP_TIMEOUT, get_cached_json

FRANKFURTER_URL = "https://api.frankfurter.app/latest"
EXCHANGE_BASE_URL = "https://api.exchangerate-api.com/v4/latest"

_CURRENCY_MAP = {
    "dolar": "USD", "usd": "USD",
    "euro": "EUR", "eur": "EUR",
    "sterlin": "GBP", "gbp": "GBP", "pound": "GBP",
    "frank": "CHF", "chf": "CHF",
    "yen": "JPY", "jpy": "JPY",
    "yuan": "CNY", "cny": "CNY",
    "ruble": "RUB", "rub": "RUB",
}


def get_exchange_rates(base: str = "USD") -> dict:
    """Fetch rates with bounded caching and fallback to a second provider."""
    base = base.upper()
    for url in (
        f"{FRANKFURTER_URL}?from={base}",
        f"{EXCHANGE_BASE_URL}/{base}",
    ):
        try:
            data = get_cached_json(
                url, timeout=DEFAULT_HTTP_TIMEOUT, cache_ttl=300, stale_ttl=0
            )
            if data:
                rates = dict(data.get("rates", {}))
                rates[base] = 1.0
                return rates
        except Exception:
            logger.exception("Döviz kuru sağlayıcısı başarısız (%s)", base)
    return {}


def is_currency_query(text: str) -> bool:
    """Return whether the input matches a supported currency lookup pattern."""
    normalized = text.lower().strip()
    if re.search(
        r"\d+[\.,]?\d*\s*(dolar|usd|euro|eur|sterlin|gbp|pound|frank|chf|yen|jpy|yuan|cny)",
        normalized,
    ):
        return True
    return any(
        word in normalized
        and any(term in normalized for term in ("ne kadar", "kaç", "fiyat", "kur", "nedir"))
        for word in _CURRENCY_MAP
    )


def convert_currency(
    amount: float,
    from_cur: str,
    to_cur: str,
    rate_lookup: Callable[[str], dict] = get_exchange_rates,
) -> str:
    """Convert a currency amount and return a formatted Turkish response."""
    from_cur = from_cur.upper().strip()
    to_cur = to_cur.upper().strip()
    rates = rate_lookup(from_cur)
    if not rates:
        return "Döviz verisi alınamadı, Efendim. Lütfen internet bağlantınızı kontrol edin."
    if to_cur not in rates:
        return f"{to_cur} kuru bulunamadı. Mevcut kurlar: {', '.join(list(rates.keys())[:10])}"

    result = amount * rates[to_cur]
    if result >= 1000:
        result_str = f"{result:,.2f}"
    elif result >= 1:
        result_str = f"{result:.4f}"
    else:
        result_str = f"{result:.6f}"
    updated = datetime.datetime.now().strftime("%H:%M")
    return (
        f"{amount:,.2f} {from_cur} = {result_str} {to_cur}\n"
        f"Kur: 1 {from_cur} = {rates[to_cur]:.4f} {to_cur}\n"
        f"Güncelleme: {updated} (Yatırım tavsiyesi değildir.)"
    )


def parse_currency_query(
    text: str,
    rate_lookup: Callable[[str], dict] = get_exchange_rates,
) -> str | None:
    """Extract a supported currency conversion request from user text."""
    normalized = text.lower().strip()
    amount_match = re.search(
        r"(\d+[\.,]?\d*)\s*(dolar|usd|euro|eur|sterlin|gbp|pound|frank|chf|yen|jpy|yuan|cny)",
        normalized,
    )
    if amount_match:
        amount = float(amount_match.group(1).replace(",", "."))
        currency = _CURRENCY_MAP.get(
            amount_match.group(2), amount_match.group(2).upper()
        )
        return convert_currency(amount, currency, "TRY", rate_lookup)

    for word, code in _CURRENCY_MAP.items():
        if word not in normalized or not any(
            term in normalized for term in ("ne kadar", "kaç", "fiyat", "kur", "nedir")
        ):
            continue
        rates = rate_lookup("USD")
        if not rates:
            return "Kur verisi alınamadı."
        if code == "USD":
            return (
                f"1 USD = {rates.get('TRY', 0):.4f} TRY\n"
                f"Güncelleme: {datetime.datetime.now().strftime('%H:%M')}\n"
                "(Yatırım tavsiyesi değildir.)"
            )
        currency_rates = rate_lookup(code)
        try_rate = currency_rates.get("TRY", 0)
        if try_rate:
            return (
                f"1 {code} = {try_rate:.4f} TRY\n"
                f"Güncelleme: {datetime.datetime.now().strftime('%H:%M')}\n"
                "(Yatırım tavsiyesi değildir.)"
            )
    return None


def format_currency_board(
    currencies: list[str],
    rate_lookup: Callable[[str], dict] = get_exchange_rates,
) -> str:
    """Format a multi-currency board using the supplied preferred currencies."""
    currencies = currencies[:6]
    try:
        rates = rate_lookup("TRY")
    except Exception:
        logger.exception("TRY bazlı kur panosu alınamadı")
        rates = {}

    if not rates:
        usd_rates = rate_lookup("USD")
        usd_try = usd_rates.get("TRY", 0)
        if not usd_try:
            return "Döviz verileri alınamadı, Efendim."
        lines = [
            "=" * 35,
            f"  KUR PANELİ — {datetime.datetime.now().strftime('%H:%M')}",
            "=" * 35,
        ]
        for currency in currencies:
            if currency == "TRY":
                continue
            rate = usd_rates.get(currency, 0)
            if rate:
                lines.append(f"  {currency}/TRY  {usd_try / rate:>10.4f}")
        lines.append("=" * 35 + "\n  (Yatırım tavsiyesi değildir.)")
        return "\n".join(lines)

    lines = [
        "=" * 35,
        f"  KUR PANELİ — {datetime.datetime.now().strftime('%H:%M')}",
        "=" * 35,
    ]
    board_currencies = [currency for currency in currencies if currency != "TRY"]

    def fetch_board_rate(currency: str) -> tuple[str, float]:
        try:
            rate = rate_lookup(currency).get("TRY", 0)
            return currency, rate
        except Exception:
            logger.exception("[Finance] %s/TRY kuru alınamadı", currency)
            return currency, 0

    with ThreadPoolExecutor(max_workers=len(board_currencies) or 1) as executor:
        for currency, try_rate in executor.map(fetch_board_rate, board_currencies):
            if try_rate:
                lines.append(f"  {currency}/TRY  {try_rate:>10.4f}")
    lines.append("=" * 35 + "\n  (Yatırım tavsiyesi değildir.)")
    return "\n".join(lines)
