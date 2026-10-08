"""Small deterministic task-plan preview for explicit and chained requests."""
from __future__ import annotations

import re
from dataclasses import dataclass

_CHAIN_SPLIT = re.compile(r"\s+(?:sonra|ardından|ardindan)\s+", re.IGNORECASE)
_PLAN_PREFIX = re.compile(r"^\s*planla\s*[:,-]?\s*", re.IGNORECASE)
_RISK_MARKERS = (
    "sil", "temizle", "gönder", "gonder", "whatsapp", "yazdır", "yazdir",
    "dosya düzenle", "dosya duzenle", "tıkla", "tikla", "klavyeye yaz",
    "aktif pencereye yaz", "alanına yaz", "alanina yaz", "kur",
)


@dataclass(frozen=True)
class PlannedStep:
    index: int
    request: str
    risk: str


@dataclass(frozen=True)
class TaskPlan:
    request: str
    steps: tuple[PlannedStep, ...]


def build_task_plan(text: str) -> TaskPlan | None:
    """Recognize an explicit `planla` request or a supported chained request."""
    request = " ".join((text or "").split())
    if not request:
        return None

    explicit = _PLAN_PREFIX.match(request)
    body = request[explicit.end():].strip() if explicit else request
    steps = [part.strip(" ,.") for part in _CHAIN_SPLIT.split(body) if part.strip(" ,.")]
    if not explicit and len(steps) < 2:
        return None
    if not steps or len(steps) > 4 or any(not step for step in steps):
        return None

    planned_steps = tuple(
        PlannedStep(
            index=index,
            request=step,
            risk=(
                "Yüksek — işlem öncesi onay gerekir"
                if any(marker in step.casefold() for marker in _RISK_MARKERS)
                else "Düşük — normal işlem"
            ),
        )
        for index, step in enumerate(steps, start=1)
    )
    return TaskPlan(request=body, steps=planned_steps)


def format_task_plan(plan: TaskPlan) -> str:
    lines = ["İşlem planı — henüz hiçbir adım çalıştırılmadı:"]
    lines.extend(
        f"{step.index}. {step.request} [{step.risk}]"
        for step in plan.steps
    )
    lines.append(
        "Planı başlatmak için 'onayla', vazgeçmek için 'iptal' yazın. "
        "Yüksek etkili adımlarda işlem öncesi ayrıca onay istenir."
    )
    return "\n".join(lines)
