"""Özellik 3 — ATLAS Arıza Giderme Akışı (state machine).

Durumlar (spec): bekleme → araştırma → uygulama → test → kullanıcı onayı →
kapanış / döngü (+ alternatif tükendi).

    WAITING ──submit(problem)──▶ RESEARCHING ──▶ APPLYING ──▶ TESTING
       ▲                             │ (sonuç yok)    │danger     │ True
       │                             ▼                ▼           ▼
       │                        EXHAUSTED   CONFIRMING(danger)   DONE
       │                             ▲           │ evet   │ hayır
       │                             │           ▼        ▼
       │◀────────────────────────────┴──── start_next() (döngü; denenmiş
       └── reset()                      EXHAUSTED        çözümler tekrar önerilmez)

Kurallar:
* ``tried`` listesi denenmiş çözümleri tutar; kuyruk ve research ``exclude``
  ile tekrar önermez.
* Zararlı adım (``is_dangerous``) uygulanmadan ÖNCE ekstra onay ister
  (``pending_danger``).
* Doğrulama otomatik değilse (``verify_fn`` → None) kullanıcıya
  "Bu çözüldü mü?" sorulur; hayır → sıradaki alternatif.
* Her adım ``log`` listesine yazılır (izlenebilirlik — geri alınabilirlik).
* Araştırma/uygulama/verify fonksiyonları enjekte edilir → saf test edilebilir.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# Zararlı işlem kalıpları — bunlar ÖNCE onay ister
DANGEROUS_PATTERNS = (
    "disk format", "format c", "diskpart", "system32", "sistem dosya",
    "bootrec", "mkfs", "fabrika ayar", "reg delete", "registry sil",
    "del /f", "rd /s", "bcdedit",
)


def is_dangerous(text: str) -> bool:
    """Metin zararlı işlem içeriyor mu (disk formatlama, sistem dosyası silme...)."""
    t = (text or "").lower()
    return any(p in t for p in DANGEROUS_PATTERNS)


class FlowState(str, Enum):
    """Arıza akışı durumları."""

    WAITING = "WAITING"          # bekleme — problem metni bekleniyor
    RESEARCHING = "RESEARCHING"  # araştırma (Web + Flash/Pro)
    APPLYING = "APPLYING"        # uygulama (klavye/fare veya bilinen yardımcılarda)
    TESTING = "TESTING"          # otomatik test
    CONFIRMING = "CONFIRMING"    # kullanıcı onayı ("çözüldü mü?"/tehlike)
    DONE = "DONE"                # çözüldü → kapanış
    EXHAUSTED = "EXHAUSTED"      # alternatif tükendi → manuel öneri


@dataclass
class Solution:
    """Tek bir aday çözüm."""

    title: str
    steps: list = field(default_factory=list)
    source_url: str = ""
    dangerous: bool = False


@dataclass
class FlowStep:
    """Akışın bir adımı — UI bununla güncellenir."""

    state: FlowState
    message: str
    solution: Solution | None = None


@dataclass
class TriedEntry:
    """Denenmiş çözüm kaydı (başarı/başarısız/atlandı)."""

    title: str
    result: str  # "ok" | "failed" | "skipped"


class TroubleshootFlow:
    """ATLAS arıza giderme state machine (saf; fonksiyonlar enjekte edilir)."""

    def __init__(self, os_name: str, research_fn, apply_fn, verify_fn,
                 research_mode: str = "flash", log_cb=None):
        """research_fn(problem, os, mode, exclude) -> (solutions, links);
        apply_fn(solution, os) -> (ok, detay); verify_fn -> bool|None."""
        self.os_name = os_name
        self.research_mode = research_mode
        self._research_fn = research_fn
        self._apply_fn = apply_fn
        self._verify_fn = verify_fn
        self._log_cb = log_cb
        self.state = FlowState.WAITING
        self.problem = ""
        self.current: Solution | None = None
        self.pending_danger = False
        self.tried: list[TriedEntry] = []
        self.resources: list[str] = []
        self.log: list[str] = []
        self._queue: deque = deque()

    # ── Yardımcılar ─────────────────────────────────────────────────────────
    @property
    def tried_titles(self) -> list[str]:
        """Denenen çözüm başlıkları (research exclude için)."""
        return [t.title for t in self.tried]

    def _write(self, msg: str) -> None:
        """Her adım izlenebilir kalsın diye damgalı log yaz."""
        entry = f"{time.strftime('%H:%M:%S')} [{self.state.value}] {msg}"
        self.log.append(entry)
        logger.info("[Troubleshoot] %s", entry)
        if self._log_cb is not None:
            try:
                self._log_cb(msg)
            except Exception:
                pass

    def _mark(self, result: str) -> None:
        if self.current is not None:
            self.tried.append(TriedEntry(self.current.title, result))

    def exhausted_message(self) -> str:
        """Tükendi mesajı: denenenler + manuel öneriler + kaynaklar."""
        lines = ["✖ Alternatif çözüm kalmadı — alternatifler tükendi."]
        if self.tried:
            lines.append("Denenenler:")
            labels = {"ok": "başarılı", "failed": "başarısız",
                      "skipped": "onaylanmadı"}
            for t in self.tried:
                lines.append(f"  • {t.title} ({labels.get(t.result, t.result)})")
        lines.append("Manuel öneriler:")
        lines.append("  • Adımları elle deneyin ya da sorunu farklı bir ifadeyle "
                     "tekrar yazın; araştırma yeniden yapılır.")
        if self.resources:
            lines.append("Kaynak linkleri:")
            for url in self.resources[:8]:
                lines.append(f"  • {url}")
        return "\n".join(lines)

    def reset(self) -> None:
        """Yeni problem için akışı başa al."""
        self.state = FlowState.WAITING
        self.problem = ""
        self.current = None
        self.pending_danger = False
        self.tried.clear()
        self.resources.clear()
        self._queue.clear()

    # ── Geçişler ────────────────────────────────────────────────────────────
    def submit(self, problem: str) -> FlowStep:
        """bekleme → araştırma → (sonuç varsa) sıradaki çözüm."""
        if self.state not in (FlowState.WAITING, FlowState.EXHAUSTED):
            raise RuntimeError(f"submit bu durumda geçersiz: {self.state.value}")
        self.state = FlowState.RESEARCHING
        self.problem = problem or ""
        self._write(f"Araştırma ({self.research_mode}): {self.problem[:80]}")
        try:
            solutions, resources = self._research_fn(
                self.problem, self.os_name, self.research_mode,
                set(self.tried_titles))
        except Exception as exc:
            logger.exception("[Troubleshoot] Araştırma hatası")
            self.state = FlowState.EXHAUSTED
            return FlowStep(self.state,
                            f"⚠ Araştırma başarısız: {exc}\n" + self.exhausted_message())
        self.resources = list(resources or [])
        exclude = set(self.tried_titles)
        self._queue = deque(s for s in solutions if s.title not in exclude)
        if not self._queue:
            self.state = FlowState.EXHAUSTED
            self._write("Çözüm bulunamadı.")
            return FlowStep(self.state, self.exhausted_message())
        self._write(f"{len(self._queue)} aday çözüm bulundu.")
        return self.start_next()

    def start_next(self) -> FlowStep:
        """Kuyruktan sıradaki denenmemiş çözüm; tükenirse EXHAUSTED."""
        while self._queue:
            sol = self._queue.popleft()
            if sol.title in self.tried_titles:
                continue
            if not sol.dangerous and any(is_dangerous(s) for s in sol.steps):
                sol.dangerous = True
            self.current = sol
            if sol.dangerous:
                self.pending_danger = True
                self.state = FlowState.APPLYING
                warn = sol.steps[0] if sol.steps else sol.title
                msg = (f"⚠ TEHLİKELİ ADIM ONAYI: '{sol.title}'\n"
                       f"İlk adım: {warn[:160]}\n"
                       f"Devam etmek için 'evet', reddetmek için 'hayır' yazın.")
                self._write(f"Tehlikeli adım onayı: {sol.title}")
                return FlowStep(self.state, msg, sol)
            self.pending_danger = False
            self.state = FlowState.APPLYING
            steps_txt = "\n".join(f"   {i}. {s[:120]}"
                                  for i, s in enumerate(sol.steps[:6], 1))
            msg = f"▶ Uygulanıyor: {sol.title}"
            if steps_txt:
                msg += f"\n{steps_txt}"
            self._write(f"Uygulama başlıyor: {sol.title}")
            return FlowStep(self.state, msg, sol)
        self.current = None
        self.pending_danger = False
        self.state = FlowState.EXHAUSTED
        self._write("Aday kuyruğu tükendi.")
        return FlowStep(self.state, self.exhausted_message())

    def approve_danger(self, approved: bool) -> FlowStep:
        """Tehlikeli adım onayı: evet → uygulamaya geç; hayır → çözümü atla."""
        if not self.pending_danger or self.current is None:
            raise RuntimeError("approve_danger beklenmeyen anda çağrıldı")
        if approved:
            self.pending_danger = False
            self._write(f"Onaylandı: {self.current.title}")
            return FlowStep(FlowState.APPLYING,
                            f"✔ Onaylandı — uygulanıyor: {self.current.title}",
                            self.current)
        self._write(f"Onaylanmadı, çözüm atlandı: {self.current.title}")
        self._mark("skipped")
        self.current = None
        return self.start_next()

    def apply_current(self) -> FlowStep:
        """Seçili çözümü uygula (her adım loglanır) → TESTING veya sıradaki."""
        if self.state is not FlowState.APPLYING or self.current is None:
            raise RuntimeError("apply_current bu durumda geçersiz")
        if self.pending_danger:
            raise RuntimeError("tehlike onayı beklenirken uygulama yapılamaz")
        sol = self.current
        try:
            ok, detail = self._apply_fn(sol, self.os_name)
        except Exception as exc:
            logger.exception("[Troubleshoot] Uygulama hatası")
            ok, detail = False, f"uygulama hatası: {exc}"
        self._write(f"Uygulama sonucu ({sol.title}): {detail}")
        if ok:
            self.state = FlowState.TESTING
            return FlowStep(self.state,
                            f"✔ Uygulandı — {detail}\nTest ediliyor...", sol)
        self._mark("failed")
        self.current = None
        return self.start_next()

    def run_test(self) -> FlowStep:
        """Otomatik test: True → DONE, False → sıradaki, None → kullanıcı sor."""
        if self.state is not FlowState.TESTING or self.current is None:
            raise RuntimeError("run_test bu durumda geçersiz")
        sol = self.current
        try:
            result = self._verify_fn(sol, self.os_name)
        except Exception:
            logger.exception("[Troubleshoot] Test hatası")
            result = None
        if result is True:
            self._mark("ok")
            self.state = FlowState.DONE
            self._write(f"Çözüm işe yaradı: {sol.title}")
            return FlowStep(self.state,
                            f"✓ Sorun çözüldü — doğrulandı: {sol.title}", sol)
        if result is False:
            self._write(f"Otomatik test başarısız: {sol.title}")
            self._mark("failed")
            self.current = None
            return self.start_next()
        self.state = FlowState.CONFIRMING
        self._write("Otomatik test yetersiz — kullanıcıya sorulacak.")
        return FlowStep(self.state,
                        f"Bu çözüldü mü? ('{sol.title}' uygulandı)\n"
                        "Lütfen 'evet' veya 'hayır' yazın.", sol)

    def user_verdict(self, solved: bool) -> FlowStep:
        """Kullanıcı onayı: evet → DONE; hayır → sıradaki alternatif (döngü)."""
        if self.state is not FlowState.CONFIRMING or self.current is None:
            raise RuntimeError("user_verdict bu durumda geçersiz")
        sol = self.current
        if solved:
            self._mark("ok")
            self.state = FlowState.DONE
            self._write(f"Kullanıcı onayı: çözüldü ({sol.title})")
            return FlowStep(self.state, "✓ Harika! Sorun çözüldü.", sol)
        self._mark("failed")
        self.current = None
        self._write("Kullanıcı 'hayır' dedi — sıradaki alternatif denenir.")
        return self.start_next()

# ── Gerçek dünyayla bağlantı (varsayılan fonksiyonlar) ──────────────────────
_EXTRACT_INSTRUCTION = (
    "Bir Windows/macOS sorun giderme uzmanısın. Verilen araştırma sonuçlarından "
    "en fazla 5 çözüm önerisi çıkar. SADECE şu JSON dizisini döndür: "
    "[{\"title\": \"kısa başlık\", \"steps\": [\"adım1\", \"adım2\"], "
    "\"dangerous\": false}] — dangerous: disk formatlama, sistem dosyası silme, "
    "registry/BCD değişikliği gibi geri dönüşü zor işlemlerse true."
)


def _extract_solutions(llm_fn, problem: str, os_name: str, report) -> list:
    """LLM'den yapılandırılmış çözüm listesi dene; olmazsa []."""
    try:
        import json as _json
        context = "\n".join(f"- {s.title}: {s.snippet[:200]} ({s.url})"
                            for s in report.sources[:12])
        raw = llm_fn(problem, _EXTRACT_INSTRUCTION, context)
        if not raw:
            return []
        start, end = raw.find("["), raw.rfind("]")
        if start < 0 or end <= start:
            return []
        items = _json.loads(raw[start:end + 1])
        out = []
        for it in items[:5]:
            if not isinstance(it, dict) or not it.get("title"):
                continue
            out.append(Solution(
                title=str(it["title"])[:120],
                steps=[str(s)[:300] for s in (it.get("steps") or [])][:8],
                dangerous=bool(it.get("dangerous", False)),
            ))
        return out
    except Exception as exc:
        logger.warning("[Troubleshoot] Çözüm çıkarma başarısız: %s", exc)
        return []


def _default_research(engine, llm_fn):
    """research_fn: ResearchEngine (Flash/Pro) + LLM çıkarma; yoksa kaynaklar."""
    def research_fn(problem: str, os_name: str, mode: str, exclude: set):
        query = f"{os_name} sorun giderme: {problem} nasıl çözülür"
        report = engine.research(query, mode, show_filters=False)
        resources = [s.url for s in report.sources][:10]
        solutions = _extract_solutions(llm_fn, problem, os_name, report) \
            if llm_fn else []
        if not solutions:  # fallback: her güvenilir kaynak bir aday
            solutions = [Solution(title=s.title,
                                  steps=[s.snippet] if s.snippet else [],
                                  source_url=s.url)
                         for s in report.sources]
        return [s for s in solutions if s.title not in exclude], resources
    return research_fn


import re as _re

_SERVICE_RE = _re.compile(r"servis(?:i)?[:\s]+([A-Za-z0-9_$.]+)", _re.IGNORECASE)
_PROCESS_RE = _re.compile(r"(?:process|süreç|program)[:\s]+([A-Za-z0-9_.\-]+)",
                          _re.IGNORECASE)


def _default_apply(solution, os_name: str):
    """Bilinen yardımcılarla uygula; eşleşmeyen adımlar manuel olarak kalır."""
    from services.troubleshoot_agent import (
        clear_temp_files, kill_process_by_name, restart_service,
    )
    executed, auto = [], 0
    for step in solution.steps:
        low = step.lower()
        result = None
        m = _SERVICE_RE.search(step)
        if m and ("servis" in low or "service" in low):
            result = restart_service(m.group(1))
        elif ("temp" in low or "geçici" in low or "önbellek" in low) and \
                ("temizle" in low or "clean" in low):
            result = clear_temp_files()
        elif "process" in low or "sonlandır" in low:
            m2 = _PROCESS_RE.search(step)
            if m2:
                result = kill_process_by_name(m2.group(1))
        if result is not None:
            auto += 1
        executed.append(str(result) if result is not None
                        else f"manuel: {step[:80]}")
    detail = "; ".join(executed[:6]) if executed else "uygulanacak adım yok"
    if auto == 0 and solution.steps:
        return True, f"Otomatik adım yok, manuel sunuldu — {detail}"
    return True, detail


def _default_verify(solution, os_name: str):
    """Programatik doğrulama mümkünse True/False; değilse None (kullanıcı sor)."""
    if os_name.lower().startswith("windows"):
        for step in solution.steps:
            m = _SERVICE_RE.search(step)
            if m and ("servis" in step.lower() or "service" in step.lower()):
                try:
                    import subprocess
                    r = subprocess.run(
                        ["sc", "query", m.group(1)],
                        capture_output=True, text=True, timeout=10)
                    if r.returncode == 0:
                        return "RUNNING" in r.stdout
                except Exception:
                    return None
    return None  # otomatik test yetersiz → "Bu çözüldü mü?"


def create_flow(os_name: str, research_mode: str = "flash",
                engine=None, llm_fn=None) -> TroubleshootFlow:
    """Gerçek fonksiyonlarla akış kur (varsayılan araştırma modu: Flash)."""
    if engine is None:
        from research_engine import get_research_engine
        engine = get_research_engine()
    if llm_fn is None:
        llm_fn = _load_default_llm()
    return TroubleshootFlow(
        os_name=os_name,
        research_fn=_default_research(engine, llm_fn),
        apply_fn=_default_apply,
        verify_fn=_default_verify,
        research_mode=research_mode,
    )


def _load_default_llm():
    """Groq varsa döndür, yoksa None (ResearchEngine şablon fallback'e düşer)."""
    try:
        from config import GROQ_API_KEY, GROQ_MODEL
        if not GROQ_API_KEY:
            return None

        def llm_fn(query, instruction, context):
            try:
                from services.ai_client import create_groq_client
                client = create_groq_client(GROQ_API_KEY)
                resp = client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[{"role": "system", "content": instruction},
                              {"role": "user",
                               "content": f"Soru: {query}\n\nKaynaklar:\n{context}"}],
                    max_tokens=1024, temperature=0.3)
                return (resp.choices[0].message.content or "").strip()
            except Exception as exc:
                logger.warning("[Troubleshoot] LLM yok: %s", exc)
                return ""
        return llm_fn
    except Exception:
        return None
