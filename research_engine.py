"""Özellik 10 — 4 Kademeli Akıllı Arama Modu: ResearchEngine.

Tek motor + mod bazlı parametreler (kod tekrarı yok):
  * flash_lite — 1-6 kaynak, ~1 sayfa, ≤5 sn; araştırmasız sorularda arama
    yapmadan anında doğrudan cevap.
  * flash      — 4-10 kaynak, ~1,5 sayfa, ~10 sn (10 kaynak).
  * pro        — 6-20 kaynak, 2-3 sayfa, ≤40 sn + GÜVENİLİRLİK analizi.
  * deep       — olabildiğince tüm kaynaklar (çoklu sayfa taraması), 10-15 dk,
                 en fazla 20 sayfa + güvenilirlik analizi.

Ortak kural: kullanıcı açıkça sayfa uzunluğu belirtirse ("3 sayfa") mod
varsayılanı yok sayılır (``parse_requested_pages`` / ``resolve_pages``).

Güvenilirlik modülü pro ve deep'te AYNI fonksiyonu kullanır. Güvensiz kaynak
raporun ana listesine ASLA girmez; güvenilir kaynak yoksa ve ayar açıksa
"Filtreler" bölümünde her kriter Evet/Hayır olarak sunulur.

Varsayımlar: 1 sayfa ≈ 500 kelime; arama kaynağı olarak DuckDuckHub HTML
(anahtarsız) kullanılır; search_fn/llm_fn enjekte edilerek çevrimdışı test
edilir.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum

from services.network import DEFAULT_HTTP_TIMEOUT, HTTP_SESSION

logger = logging.getLogger(__name__)

WORDS_PER_PAGE = 500        # varsayım: 1 sayfa ≈ 500 kelime
MAX_PAGES = 20              # hiçbir mod 20 sayfayı aşamaz (deep üst sınırı)


class ResearchMode(str, Enum):
    """Araştırma modu anahtarları (UI dropdown ile eşleşir)."""

    FLASH_LITE = "flash_lite"
    FLASH = "flash"
    PRO = "pro"
    DEEP = "deep"


@dataclass(frozen=True)
class ModeParams:
    """Modun sabit parametreleri — motor yalnızca bunları okur."""

    key: str
    label: str
    min_sources: int
    max_sources: int
    target_pages: float      # varsayılan rapor uzunluğu (sayfa)
    per_source: float = 1.0  # kaynak başına saniye (bütçe hesabı)
    max_total_s: float = 60  # mutlak tavan (sn)
    reliability: bool = False      # güvenilirlik analizi (pro/deep)
    search_page_size: int = 30     # arama sayfası başına sonuç
    max_search_pages: int = 1      # tarama sayfası (deep çoklu)

    @property
    def estimate_s(self) -> float:
        """Tahmini süre (geri sayım + bütçe): per_source × max_sources, tavanda kesilir."""
        return min(self.max_total_s, self.per_source * self.max_sources)


MODES: dict[str, ModeParams] = {
    ResearchMode.FLASH_LITE.value: ModeParams(
        key="flash_lite", label="Flash Lite", min_sources=1, max_sources=6,
        target_pages=1.0, per_source=0.8, max_total_s=5.0),
    ResearchMode.FLASH.value: ModeParams(
        key="flash", label="Flash", min_sources=4, max_sources=10,
        target_pages=1.5, per_source=1.0, max_total_s=15.0),
    ResearchMode.PRO.value: ModeParams(
        key="pro", label="Pro", min_sources=6, max_sources=20,
        target_pages=3.0, per_source=2.0, max_total_s=40.0,
        reliability=True),
    ResearchMode.DEEP.value: ModeParams(
        key="deep", label="Deep Research", min_sources=10, max_sources=200,
        target_pages=10.0, per_source=4.0, max_total_s=900.0,
        reliability=True, search_page_size=30, max_search_pages=10),
}


def compute_budget(params: ModeParams, planned_sources: int) -> float:
    """Bütçe = min(mutlak tavan, kaynak başına süre × planlanan kaynak)."""
    return min(params.max_total_s, params.per_source * max(1, planned_sources))


def resolve_pages(params: ModeParams, requested_pages: float | None) -> float:
    """Sayfa uzunluğu: kullanıcı isteği mod varsayılanını geçersiz kılar (1..20)."""
    pages = float(requested_pages) if requested_pages is not None else params.target_pages
    return max(1.0, min(float(MAX_PAGES), pages))


_PAGE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*sayfa", re.IGNORECASE)


def parse_requested_pages(text: str) -> float | None:
    """'3 sayfa istiyorum' gibi ifadelerden sayfa sayısını çıkarır."""
    m = _PAGE_RE.search(text or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


_RESEARCH_MARKERS = (
    "bugün", "güncel", "son dakika", "haber", "fiyat", "kur", "borsa",
    "hisse", "istatistik", "seçim", "maç", "sonuç", "trend", "popüler",
    "en son", "2024", "2025", "2026", "araştır", "incele", "karşılaştır",
    "nasıl yapılır", "hava durumu", "dakika", "saat kaçta",
)


def requires_research(text: str) -> bool:
    """Soru web araştırması istiyor mu? (Flash Lite doğrudan cevap kuralı)

    Genel bilgi soruları (ör. 'photosynthesis nedir') araştırmaz → milisaniyeler
    içinde doğrudan cevap.
    """
    t = (text or "").lower()
    return any(marker in t for marker in _RESEARCH_MARKERS)


# ── Kaynak + güvenilirlik (pro & deep ORTAK — kod tekrarı yok) ──────────────
@dataclass
class Source:
    """Tek bir arama sonucu."""

    url: str
    title: str
    snippet: str = ""
    age_days: int | None = None  # bilinmiyorsa None (tazelik kriterleri True)


_OFFICIAL_SUFFIX = (".gov", ".gov.tr", ".edu", ".edu.tr", ".mil", ".int")
_OFFICIAL_DOMAINS = {
    "who.int", "un.org", "europa.eu", "iso.org", "oecd.org", "imf.org",
    "worldbank.org", "tubitak.gov.tr", "meb.gov.tr", "tuik.gov.tr",
}
_ACADEMIC_JOURNALS = {
    "nature.com", "sciencedirect.com", "springer.com", "link.springer.com",
    "wiley.com", "onlinelibrary.wiley.com", "ieee.org", "ieeexplore.ieee.org",
    "arxiv.org", "ncbi.nlm.nih.gov", "plos.org", "acs.org", "rsc.org",
    "jstor.org", "ssrn.com",
}
_ACADEMIC_SUFFIX = ("ac.uk", "ac.jp", "edu.tr")
_NEWS_DOMAINS = {
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "bloomberg.com",
    "cnbc.com", "ft.com", "economist.com", "theguardian.com", "nytimes.com",
    "wsj.com", "aa.com.tr", "trthaber.com", "ntv.com.tr", "hurriyet.com.tr",
    "milliyet.com.tr",
}
_LOW_TRUST_DOMAINS = {
    "reddit.com", "quora.com", "scribd.com", "slideshare.net", "yahoo.com",
    "pinterest.com", "tiktok.com", "instagram.com", "facebook.com",
    "twitter.com", "x.com", "blogspot.com", "wordpress.com", "medium.com",
    "wixsite.com", "youtube.com",
}

CRITERIA_LABELS = (
    "Bilimsel/akademik",
    "Genel olarak güvenilir",
    "Hakem/editör değerlendirmesinden geçmiş",
    "Bağımsız uzman incelemesi var",
    "Son gelişmeleri yansıtıyor",
    "Güncel",
)
TRUSTED_MIN = 4  # 6 kriterden en az 4'ü "Evet" → güvenilir


def _domain_of(url: str) -> str:
    try:
        host = url.split("//", 1)[-1].split("/", 1)[0].lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _source_type(domain: str) -> str:
    if any(domain == d or domain.endswith("." + d) for d in _ACADEMIC_JOURNALS) \
            or domain.endswith(_ACADEMIC_SUFFIX):
        return "akademik"
    if domain.endswith(_OFFICIAL_SUFFIX) or domain in _OFFICIAL_DOMAINS:
        return "resmi kurum"
    if domain in _NEWS_DOMAINS or any(
            domain.endswith("." + d) for d in _NEWS_DOMAINS):
        return "haber"
    if any(d in domain for d in _LOW_TRUST_DOMAINS):
        return "forum/blog/sosyal"
    return "diğer"


@dataclass
class ReliabilityReport:
    """Bir kaynağın kriter kriter güvenilirlik analizi (Evet/Hayır)."""

    source_type: str
    criteria: dict          # CRITERIA_LABELS → bool
    trusted: bool

    @property
    def score(self) -> int:
        """'Evet' olan kriter sayısı (0..6)."""
        return sum(1 for v in self.criteria.values() if v)


def evaluate_source(source: Source) -> ReliabilityReport:
    """6 kriterle kaynağı değerlendir (pro ve deep'te tek fonksiyon)."""
    domain = _domain_of(source.url)
    stype = _source_type(domain)
    academic = stype == "akademik"
    official = stype == "resmi kurum"
    news = stype == "haber"
    low = stype == "forum/blog/sosyal"
    peer_or_editor = domain in _ACADEMIC_JOURNALS or news
    criteria = {
        "Bilimsel/akademik": academic,
        "Genel olarak güvenilir": (academic or official or news) and not low,
        "Hakem/editör değerlendirmesinden geçmiş": peer_or_editor,
        "Bağımsız uzman incelemesi var": academic or official or news,
        "Son gelişmeleri yansıtıyor": source.age_days is None
        or source.age_days <= 90,
        "Güncel": source.age_days is None or source.age_days <= 30,
    }
    score = sum(1 for v in criteria.values() if v)
    return ReliabilityReport(source_type=stype, criteria=criteria,
                             trusted=score >= TRUSTED_MIN)


def evaluate_sources(sources: list[Source]) -> tuple[list, list]:
    """Listeyi (güvenilir, [(kaynak, analiz)... elenen]) olarak böler."""
    trusted, excluded = [], []
    for src in sources:
        report = evaluate_source(src)
        if report.trusted:
            trusted.append(src)
        else:
            excluded.append((src, report))
    return trusted, excluded


# ── Rapor ────────────────────────────────────────────────────────────────────
@dataclass
class ResearchReport:
    """Araştırma sonucu — motor üretir, format_report metni render eder."""

    mode_label: str
    query: str
    pages: float
    target_words: int
    examined: int = 0
    direct: bool = False
    sources: list = field(default_factory=list)          # [Source] güvenilir
    excluded: list = field(default_factory=list)         # [(Source, ReliabilityReport)]
    summary: str = ""
    text: str = ""
    budget_s: float = 0.0


_SUMMARY_INSTRUCTION = (
    "Sen bir araştırma raporlusun. Verilen kaynaklardan Türkçe, dengeli bir "
    "derleme yaz. Uzunluk hedefi: ~{words} kelime (~{pages:g} sayfa). Yalnızca "
    "sağlanan kaynaklara dayan; kaynak yoksa uydurma. Madde madde yaz."
)
_DIRECT_INSTRUCTION = (
    "Kısa ve doğru, tek paragraflık doğrudan cevap yaz. Web araştırması yapılmadı."
)


def format_report(report: ResearchReport, show_filters: bool = True) -> str:
    """Raporu kullanıcı metnine çevir (Filtreler ayarıyla)."""
    if report.direct:
        return report.text
    lines = [
        f"📋 {report.mode_label} RAPORU",
        f"Soru: {report.query}",
        f"Kaynak: {report.examined} incelendi → {len(report.sources)} güvenilir "
        f"kabul | Uzunluk: ~{report.pages:g} sayfa (~{report.target_words} kelime)",
        "",
    ]
    if not report.sources:
        if report.excluded:
            if show_filters:
                lines.append(
                    "Güvenilir kaynak bulunamadı; düşük güvenilirlikli kaynaklar "
                    "aşağıda (Filtreler).")
            else:
                lines.append(
                    "Güvenilir kaynak bulunamadı. Düşük güvenilirlikli kaynaklar "
                    "ayar gereği gizlendi.")
        else:
            lines.append("Sonuç bulunamadı; internet bağlantısını kontrol edin.")
    else:
        lines += ["## Özet"]
        lines.append(report.summary or "\n".join(
            f"- {s.title}: {s.snippet[:160] or s.url}"
            for s in report.sources[:8]))
        lines += ["", "## Kaynaklar"]
        for i, src in enumerate(report.sources, 1):
            lines.append(f"{i}. {src.title} — {src.url}")
        if report.excluded:
            lines.append(
                f"\n_Not: {len(report.excluded)} kaynak güvenilirlik "
                f"filtresiyle elendi (rapora dahil edilmez)._")
    if report.excluded and show_filters and not report.sources:
        lines += ["", "## Filtreler",
                  "Bu kaynaklar güvenilir bulunmadı; her kriter Evet/Hayır:"]
        for i, (src, rel) in enumerate(report.excluded, 1):
            lines.append(f"{i}. {src.title} — {src.url}")
            lines.append(f"   Kaynak türü: {rel.source_type}")
            for label in CRITERIA_LABELS:
                verdict = "Evet" if rel.criteria[label] else "Hayır"
                lines.append(f"   - {label}: {verdict}")
    return "\n".join(lines)


# ── Motor ─────────────────────────────────────────────────────────────────────
class ResearchEngine:
    """Tek motor; mod farkı yalnızca ModeParams (kod tekrarı yok)."""

    def __init__(self, search_fn=None, llm_fn=None):
        self._search_fn = search_fn or _ddg_search
        self.llm_fn = llm_fn  # opsiyonel: (query, instruction, context) -> str

    def research(self, query: str, mode, requested_pages: float | None = None,
                 show_filters: bool = True, progress_cb=None,
                 cancel=None, response_callback=None) -> ResearchReport:
        """Modda araştırma yap; ``ResearchReport.text`` hazır döner."""
        key = mode.value if isinstance(mode, ResearchMode) else str(mode)
        params = MODES[key]
        pages = resolve_pages(params, requested_pages)
        target_words = int(pages * WORDS_PER_PAGE)
        budget = compute_budget(params, params.max_sources)

        # Flash Lite: araştırmasız soru → arama yapmadan anında cevap
        if params.key == ResearchMode.FLASH_LITE.value and not requires_research(query):
            answer = self._llm(query, _DIRECT_INSTRUCTION, "") or (
                "Doğrudan cevap (web araştırması gerekmedi):\n"
                f"{query}\n\nBu genel bilgi sorusu için arama yapılmadı.")
            return ResearchReport(
                mode_label=params.label, query=query, pages=1.0,
                target_words=target_words, direct=True, text=answer,
                budget_s=budget)

        deadline = time.monotonic() + budget
        collected: dict = {}
        pages_fetched = 0
        planned = params.max_sources
        while (pages_fetched < params.max_search_pages
               and len(collected) < params.max_sources
               and time.monotonic() < deadline
               and not (cancel is not None and cancel.is_set())):
            try:
                search_args = (
                    query, params.search_page_size,
                    pages_fetched * params.search_page_size,
                )
                if self._search_fn is _ddg_search:
                    batch = self._search_fn(
                        *search_args,
                        cancel_event=cancel,
                        response_callback=response_callback,
                    ) or []
                else:
                    batch = self._search_fn(*search_args) or []
            except Exception as exc:
                if cancel is not None and cancel.is_set():
                    break
                logger.warning("[Research] Arama hatası: %s", exc)
                break
            if cancel is not None and cancel.is_set():
                break
            if not batch:
                break
            for src in batch:
                collected.setdefault(src.url, src)
            pages_fetched += 1
            if progress_cb is not None:
                try:
                    progress_cb(min(len(collected), planned), planned)
                except Exception:
                    pass

        sources = list(collected.values())[:params.max_sources]
        if params.reliability:
            trusted, excluded = evaluate_sources(sources)
        else:
            trusted, excluded = list(sources), []

        summary = ""
        if trusted and not (cancel is not None and cancel.is_set()):
            context = "\n".join(
                f"- {s.title}: {s.snippet[:200]} ({s.url})"
                for s in trusted[:25])
            summary = self._llm(
                query,
                _SUMMARY_INSTRUCTION.format(words=target_words, pages=pages),
                context) or ""

        report = ResearchReport(
            mode_label=params.label, query=query, pages=pages,
            target_words=target_words, examined=len(sources),
            sources=trusted, excluded=excluded, summary=summary,
            budget_s=budget)
        report.text = format_report(report, show_filters=show_filters)
        logger.info("[Research] %s: %d kaynak (%d elendi), %.1fs bütçe",
                    params.label, len(trusted), len(excluded), budget)
        return report

    def _llm(self, query: str, instruction: str, context: str) -> str:
        """LLM varsa kullan, yoksa boş dön (şablon fallback)."""
        if self.llm_fn is None:
            return ""
        try:
            return (self.llm_fn(query, instruction, context) or "").strip()
        except Exception as exc:
            logger.warning("[Research] LLM özeti başarısız: %s", exc)
            return ""


# ── Varsayılan arama: DuckDuckGo HTML (anahtarsız) ──────────────────────────
def _ddg_search(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    cancel_event=None,
    response_callback=None,
) -> list:
    """DuckDuckGo HTML sonucu → [Source]; hata/engel → []."""
    try:
        from urllib.parse import parse_qs, quote, unquote, urlparse

        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("[Research] bs4 yok — arama devre dışı.")
        return []
    try:
        url = f"https://html.duckduckgo.com/html/?q={quote(query)}&s={int(offset)}"
        if HTTP_SESSION is None:
            logger.warning("[Research] requests yok — arama devre dışı.")
            return []
        resp = None
        try:
            resp = HTTP_SESSION.get(
                url, timeout=DEFAULT_HTTP_TIMEOUT, stream=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; JARVIS/10.0)"})
            if response_callback is not None:
                response_callback(resp)
            if cancel_event is not None and cancel_event.is_set():
                return []
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
        finally:
            if response_callback is not None and resp is not None:
                response_callback(None)
            if resp is not None:
                resp.close()
        out = []
        for a in soup.select("a.result__a")[:max_results]:
            href = a.get("href", "")
            if "uddg=" in href:
                real = unquote(
                    parse_qs(urlparse(href).query).get("uddg", [""])[0])
            else:
                real = href
            if not real.startswith("http"):
                continue
            out.append(Source(url=real,
                              title=a.get_text(" ", strip=True)[:200],
                              snippet=""))
        for i, sn in enumerate(soup.select(".result__snippet")[:len(out)]):
            out[i].snippet = sn.get_text(" ", strip=True)[:300]
        return out
    except Exception as exc:
        logger.warning("[Research] DDG arama başarısız: %s", exc)
        return []


# ── Singleton ────────────────────────────────────────────────────────────────
_engine_instance: ResearchEngine | None = None


def get_research_engine() -> ResearchEngine:
    """Paylaşılan motor (tek UI erişimi; worker thread'den çağrılır)."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ResearchEngine()
    return _engine_instance
