"""
JARVIS v10 APEX PRIME — Agent Orkestrasyon Katmanı
===================================================
Karmaşık, çok adımlı görevleri planlayıp yürütür.
Örnek: "şu siteden veri çek, Excel'e yaz, bana özet çıkar"
       → [web_scrape, excel_write, ai_summarize] adımlarına böler.

Özellikler:
  • AI ile görev planlaması
  • Adımlar arası bağlam aktarımı
  • Hata → alternatif dene → kullanıcıya bildir → resume desteği
  • SQLite'a kayıt (uygulama kapanıp açılsa devam et)
  • İlerleme callback (UI QProgressBar için)
"""
from __future__ import annotations

import datetime
import json
import os
import time
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from logger_setup import logger

# ── Veri modelleri ────────────────────────────────────────────────────────

class StepStatus(str, Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    DONE     = "done"
    FAILED   = "failed"
    SKIPPED  = "skipped"


@dataclass
class TaskStep:
    step_id:     str
    description: str
    service:     str          # "web_automation" | "code_agent" | "ai_chat" | "system" vb.
    action:      str          # Servis içindeki fonksiyon adı
    params:      dict         = field(default_factory=dict)
    status:      StepStatus   = StepStatus.PENDING
    result:      Any          = None
    error:       str          = ""
    retry_count: int          = 0
    max_retries: int          = 2


@dataclass
class TaskPlan:
    plan_id:     str
    goal:        str
    steps:       list[TaskStep]
    status:      StepStatus  = StepStatus.PENDING
    context:     dict        = field(default_factory=dict)  # Adımlar arası veri taşıyıcı
    created_at:  str         = field(default_factory=lambda: datetime.datetime.now().isoformat())
    updated_at:  str         = field(default_factory=lambda: datetime.datetime.now().isoformat())


# ── SQLite kalıcılığı ─────────────────────────────────────────────────────

APP_DATA_DIR = Path.home() / ".jarvis"

def _get_db_path() -> str:
    try:
        from config import DB_PATH
        return DB_PATH
    except ImportError:
        return str(APP_DATA_DIR / "jarvis_memory.db")


def _ensure_tables():
    import sqlite3
    con = sqlite3.connect(_get_db_path())
    con.execute("""
        CREATE TABLE IF NOT EXISTS task_plans (
            plan_id TEXT PRIMARY KEY,
            goal TEXT,
            steps_json TEXT,
            status TEXT,
            context_json TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    con.commit()
    con.close()


def _save_plan(plan: TaskPlan):
    import sqlite3
    try:
        _ensure_tables()
        steps_json = json.dumps([{
            "step_id": s.step_id, "description": s.description,
            "service": s.service, "action": s.action, "params": s.params,
            "status": s.status.value, "result": str(s.result)[:1000] if s.result else None,
            "error": s.error, "retry_count": s.retry_count, "max_retries": s.max_retries,
        } for s in plan.steps])
        plan.updated_at = datetime.datetime.now().isoformat()
        con = sqlite3.connect(_get_db_path())
        con.execute("""
            INSERT OR REPLACE INTO task_plans
            (plan_id, goal, steps_json, status, context_json, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?)
        """, (plan.plan_id, plan.goal, steps_json, plan.status.value,
              json.dumps(plan.context), plan.created_at, plan.updated_at))
        con.commit()
        con.close()
    except Exception as exc:
        logger.warning("[AgentCore] Plan kayıt hatası: %s", exc)


def _load_plan(plan_id: str) -> Optional[TaskPlan]:
    import sqlite3
    try:
        con = sqlite3.connect(_get_db_path())
        row = con.execute(
            "SELECT * FROM task_plans WHERE plan_id=?", (plan_id,)
        ).fetchone()
        con.close()
        if not row:
            return None
        steps_raw = json.loads(row[2])
        steps = [TaskStep(
            step_id=s["step_id"], description=s["description"],
            service=s["service"], action=s["action"], params=s["params"],
            status=StepStatus(s["status"]), result=s.get("result"),
            error=s.get("error", ""), retry_count=s.get("retry_count", 0),
            max_retries=s.get("max_retries", 2),
        ) for s in steps_raw]
        return TaskPlan(
            plan_id=row[0], goal=row[1], steps=steps,
            status=StepStatus(row[3]),
            context=json.loads(row[4]) if row[4] else {},
            created_at=row[5], updated_at=row[6],
        )
    except Exception as exc:
        logger.warning("[AgentCore] Plan yükle hatası: %s", exc)
        return None


# ── Servis çalıştırıcı ────────────────────────────────────────────────────

class ServiceExecutor:
    """
    TaskStep.service + action → gerçek fonksiyon çağrısı.
    Yeni servisler buraya eklenerek genişletilir.
    """

    def __init__(self, router=None):
        self._router = router

    def execute(self, step: TaskStep, context: dict) -> Any:
        """Adımı çalıştırır, sonucu döndürür."""
        # Params içindeki {{key}} ifadelerini context ile doldur
        params = self._resolve_params(step.params, context)

        service = step.service.lower()
        action  = step.action.lower()

        if service == "ai_chat":
            return self._run_ai_chat(action, params, context)
        elif service == "web_automation":
            return self._run_web(action, params)
        elif service == "computer_control":
            return self._run_computer(action, params)
        elif service == "code_agent":
            return self._run_code_agent(action, params)
        elif service == "system":
            return self._run_system(action, params)
        elif service == "file":
            return self._run_file(action, params)
        else:
            raise ValueError(f"Bilinmeyen servis: {service}")

    def _resolve_params(self, params: dict, context: dict) -> dict:
        """{{step_1_result}} gibi şablonları doldur."""
        resolved = {}
        for k, v in params.items():
            if isinstance(v, str):
                for ctx_key, ctx_val in context.items():
                    v = v.replace(f"{{{{{ctx_key}}}}}", str(ctx_val)[:2000])
            resolved[k] = v
        return resolved

    def _run_ai_chat(self, action: str, params: dict, context: dict) -> str:
        prompt = params.get("prompt", "")
        system = params.get("system", "")
        if self._router:
            from services.model_router import TaskType
            task_type_map = {"code": TaskType.CODE, "long": TaskType.LONG_CONTEXT}
            tt = task_type_map.get(params.get("task_type", ""), TaskType.CHAT)
            return self._router.chat([], prompt, system, task_type=tt)
        else:
            try:
                from services.ai_client import create_groq_client
                key = os.environ.get("JARVIS_GROQ_API_KEY") or os.environ.get("GROQ_API_KEY", "")
                client = create_groq_client(key)
                resp = client.chat.completions.create(
                    model=os.environ.get("JARVIS_GROQ_MODEL", "openai/gpt-oss-20b"),
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": prompt}],
                    max_tokens=1024, temperature=0.7)
                return resp.choices[0].message.content
            except Exception as exc:
                raise RuntimeError(f"AI chat hatası: {exc}")

    def _run_web(self, action: str, params: dict) -> str:
        from services.web_automation import open_url, interact
        if action == "open_url":
            return open_url(params.get("url", ""))
        elif action == "interact":
            return interact(params.get("url", ""), params.get("action_type", "click"),
                           params.get("target", ""), params.get("value", ""))
        raise ValueError(f"web_automation: bilinmeyen action: {action}")

    def _run_computer(self, action: str, params: dict) -> str:
        from services.computer_control import click_screen, type_text, capture_screen, analyze_screen
        if action == "click":
            return click_screen(int(params.get("x", 0)), int(params.get("y", 0)))
        elif action == "type":
            return type_text(params.get("text", ""))
        elif action == "screenshot":
            return capture_screen()
        elif action == "analyze":
            return analyze_screen()
        raise ValueError(f"computer_control: bilinmeyen action: {action}")

    def _run_code_agent(self, action: str, params: dict) -> str:
        from services.code_agent import CodeAgent
        agent = CodeAgent(router=self._router)
        if action == "execute_task":
            return agent.execute_task(
                project_dir=params.get("project_dir", "."),
                task=params.get("task", ""),
                auto_approve=params.get("auto_approve", False),
            )
        elif action == "undo":
            return agent.undo_last_changes(params.get("project_dir", "."))
        raise ValueError(f"code_agent: bilinmeyen action: {action}")

    def _run_system(self, action: str, params: dict) -> str:
        import subprocess
        if action == "run_command":
            cmd = params.get("command", "").split()
            if not cmd:
                return "Komut boş."
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=30, shell=False)
            return result.stdout[:2000] or result.stderr[:1000]
        raise ValueError(f"system: bilinmeyen action: {action}")

    def _run_file(self, action: str, params: dict) -> str:
        from pathlib import Path as P
        if action == "read":
            path = P(params.get("path", ""))
            return path.read_text(encoding="utf-8", errors="ignore")[:5000]
        elif action == "write":
            path = P(params.get("path", ""))
            path.write_text(params.get("content", ""), encoding="utf-8")
            return f"Dosya yazıldı: {path}"
        raise ValueError(f"file: bilinmeyen action: {action}")


# ── AI plan oluşturucu ───────────────────────────────────────────────────

def create_plan_from_goal(goal: str, router=None) -> TaskPlan:
    """
    Kullanıcının hedefinden AI ile adım adım plan oluşturur.
    """
    system_prompt = """Sen bir görev planlayıcısısın. 
Kullanıcının hedefini alıp bunu JSON formatında adımlara böl.

Her adım şu yapıda olmalı:
{
  "steps": [
    {
      "description": "Türkçe açıklama",
      "service": "ai_chat|web_automation|computer_control|code_agent|system|file",
      "action": "fonksiyon_adı",
      "params": {}
    }
  ]
}

Desteklenen servis/action çiftleri:
- ai_chat / chat: {prompt, system, task_type}
- web_automation / open_url: {url}
- web_automation / interact: {url, action_type, target, value}
- computer_control / click: {x, y}
- computer_control / type: {text}
- computer_control / screenshot: {}
- computer_control / analyze: {}
- code_agent / execute_task: {project_dir, task}
- system / run_command: {command}
- file / read: {path}
- file / write: {path, content}

Bir adımın sonucu, sonraki adımda {{step_N_result}} şablonuyla kullanılabilir.
Sadece JSON döndür, başka açıklama ekleme."""

    if router:
        from services.model_router import TaskType
        response = router.chat([], goal, system_prompt, task_type=TaskType.CHAT)
    else:
        try:
            from services.ai_client import create_groq_client
            key = os.environ.get("JARVIS_GROQ_API_KEY") or os.environ.get("GROQ_API_KEY", "")
            client = create_groq_client(key)
            resp = client.chat.completions.create(
                model=os.environ.get("JARVIS_GROQ_MODEL", "openai/gpt-oss-20b"),
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": goal}],
                max_tokens=1024, temperature=0.3)
            response = resp.choices[0].message.content
        except Exception as exc:
            # Hata durumunda tek adımlı AI chat planı oluştur
            logger.debug("[AgentCore] Plan üretilemedi, AI chat fallback: %s", exc)
            return TaskPlan(
                plan_id=str(uuid.uuid4()),
                goal=goal,
                steps=[TaskStep(
                    step_id="step_1",
                    description=goal,
                    service="ai_chat",
                    action="chat",
                    params={"prompt": goal, "system": "JARVIS AI asistanısın. Türkçe konuş."},
                )]
            )

    # JSON çıkart
    try:
        import re
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            steps = []
            for i, s in enumerate(data.get("steps", []), 1):
                steps.append(TaskStep(
                    step_id=f"step_{i}",
                    description=s.get("description", f"Adım {i}"),
                    service=s.get("service", "ai_chat"),
                    action=s.get("action", "chat"),
                    params=s.get("params", {}),
                ))
            return TaskPlan(plan_id=str(uuid.uuid4()), goal=goal, steps=steps)
    except Exception:
        pass

    # Fallback: tek adım
    return TaskPlan(
        plan_id=str(uuid.uuid4()),
        goal=goal,
        steps=[TaskStep(
            step_id="step_1",
            description=goal,
            service="ai_chat",
            action="chat",
            params={"prompt": goal, "system": "JARVIS AI asistanısın. Türkçe konuş."},
        )]
    )


# ── Ana AgentCore ─────────────────────────────────────────────────────────

class AgentCore:
    """
    Çok adımlı görev orkestratörü.
    
    Kullanım:
        agent = AgentCore(router=get_router())
        for update in agent.run_goal("şu siteden veri çek ve özetle"):
            print(update)
    """

    def __init__(self, router=None):
        self._router = router
        self._executor = ServiceExecutor(router)
        self._running_plan: Optional[TaskPlan] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    def run_goal(
        self,
        goal: str,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
        notify_cb: Optional[Callable[[str], None]] = None,
    ) -> Iterator[str]:
        """
        Hedeften plan oluşturup yürütür.
        Yields: İlerleme mesajları
        """
        self._stop_event.clear()

        yield f"Görev analiz ediliyor: {goal}"

        # Plan oluştur
        plan = create_plan_from_goal(goal, self._router)
        self._running_plan = plan
        _save_plan(plan)

        total = len(plan.steps)
        yield f"Plan hazır: {total} adım"
        for i, step in enumerate(plan.steps, 1):
            yield f"  {i}. {step.description}"

        # Adımları yürüt
        for i, step in enumerate(plan.steps, 1):
            if self._stop_event.is_set():
                yield "Görev kullanıcı tarafından durduruldu."
                break

            yield f"\n[{i}/{total}] {step.description}"
            if progress_cb:
                progress_cb(i, total, step.description)

            step.status = StepStatus.RUNNING
            _save_plan(plan)

            for attempt in range(step.max_retries + 1):
                if self._stop_event.is_set():
                    break
                try:
                    result = self._executor.execute(step, plan.context)
                    step.result = result
                    step.status = StepStatus.DONE
                    # Sonucu context'e ekle
                    plan.context[f"step_{i}_result"] = str(result)[:3000]
                    _save_plan(plan)
                    yield f"  ✓ Tamamlandı: {str(result)[:200]}"
                    break
                except Exception as exc:
                    step.retry_count += 1
                    step.error = str(exc)
                    logger.warning("[AgentCore] Adım %d başarısız (deneme %d): %s", i, attempt+1, exc)
                    if attempt < step.max_retries:
                        yield f"  ⚠ Hata: {exc} — yeniden deneniyor ({attempt+2}/{step.max_retries+1})..."
                        time.sleep(1)
                    else:
                        step.status = StepStatus.FAILED
                        _save_plan(plan)
                        if notify_cb:
                            notify_cb(f"Adım {i} başarısız: {exc}")
                        yield f"  ✗ Adım başarısız: {exc}"
                        yield "  (Sonraki adıma devam ediliyor...)"

        # Özet
        plan.status = StepStatus.DONE
        _save_plan(plan)
        done = sum(1 for s in plan.steps if s.status == StepStatus.DONE)
        failed = sum(1 for s in plan.steps if s.status == StepStatus.FAILED)
        yield f"\n══ GÖREV TAMAMLANDI ══"
        yield f"Başarılı: {done}/{total} adım"
        if failed:
            yield f"Başarısız: {failed} adım"

        # Son adımın sonucunu özet olarak döndür
        last_done = next((s for s in reversed(plan.steps) if s.status == StepStatus.DONE), None)
        if last_done and last_done.result:
            yield f"\nSonuç:\n{str(last_done.result)[:1000]}"

    def stop(self):
        """Çalışan görevi durdur."""
        self._stop_event.set()

    def resume_plan(
        self,
        plan_id: str,
        progress_cb=None,
        notify_cb=None,
    ) -> Iterator[str]:
        """Yarıda kalan planı devam ettirir."""
        plan = _load_plan(plan_id)
        if not plan:
            yield f"Plan bulunamadı: {plan_id}"
            return
        # Tamamlanmamış adımları yeniden yürüt
        pending_steps = [s for s in plan.steps if s.status in {StepStatus.PENDING, StepStatus.FAILED}]
        yield f"Devam edilen plan: {plan.goal} ({len(pending_steps)} adım kaldı)"
        for i, step in enumerate(pending_steps, 1):
            if self._stop_event.is_set():
                break
            total = len(pending_steps)
            yield f"\n[{i}/{total}] {step.description}"
            if progress_cb:
                progress_cb(i, total, step.description)
            try:
                result = self._executor.execute(step, plan.context)
                step.result = result
                step.status = StepStatus.DONE
                plan.context[f"{step.step_id}_result"] = str(result)[:3000]
                _save_plan(plan)
                yield f"  ✓ {str(result)[:200]}"
            except Exception as exc:
                step.status = StepStatus.FAILED
                _save_plan(plan)
                yield f"  ✗ Hata: {exc}"

    def get_pending_plans(self) -> list[dict]:
        """Tamamlanmamış planları listeler."""
        try:
            import sqlite3
            _ensure_tables()
            con = sqlite3.connect(_get_db_path())
            rows = con.execute(
                "SELECT plan_id, goal, status, created_at FROM task_plans "
                "WHERE status NOT IN ('done','failed') ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
            con.close()
            return [{"plan_id": r[0], "goal": r[1], "status": r[2], "created_at": r[3]} for r in rows]
        except Exception:
            return []


# ── Yardımcı: doğal dilde çok adımlı görev mi? ──────────────────────────

def is_multi_step_goal(text: str) -> bool:
    """Kullanıcı metninin çok adımlı bir görev olup olmadığını tahmin eder."""
    indicators = [
        " sonra ", " ardından ", " ardindan ", " ve sonra ", " daha sonra ",
        " bunu yaptıktan sonra ", " birinci ", " ikinci ",
        "çek ve ", "al ve ", "yaz ve ", "bul ve ",
        "önce ", "then ", "after that",
    ]
    t = text.lower()
    # En az 2 fiil veya bağlaç içeriyorsa çok adımlı sayılır
    count = sum(1 for ind in indicators if ind in t)
    return count >= 1 and len(text) > 40
