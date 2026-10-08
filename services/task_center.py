"""Thread-safe in-memory task and step lifecycle for the JARVIS task center."""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskStep:
    title: str
    skill_id: str = ""
    status: StepStatus = StepStatus.QUEUED
    message: str = ""


@dataclass
class TaskRecord:
    task_id: str
    title: str
    status: TaskStatus
    steps: list[TaskStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    message: str = ""
    cancel_callback: Callable[[], None] | None = field(default=None, repr=False)


class TaskCenter:
    """Maintain a bounded, observable history of task and step state."""

    def __init__(self, history_limit: int = 50):
        if history_limit < 1:
            raise ValueError("Görev geçmişi sınırı en az bir olmalı.")
        self._history_limit = history_limit
        self._records: list[TaskRecord] = []
        self._lock = threading.RLock()

    def create(
        self,
        title: str,
        steps: list[tuple[str, str]] | None = None,
        cancel_callback: Callable[[], None] | None = None,
    ) -> str:
        clean_title = " ".join((title or "").split())[:300]
        if not clean_title:
            raise ValueError("Görev adı boş olamaz.")
        record = TaskRecord(
            task_id=uuid.uuid4().hex,
            title=clean_title,
            status=TaskStatus.QUEUED,
            steps=[TaskStep(title, skill_id) for title, skill_id in (steps or [])],
            cancel_callback=cancel_callback,
        )
        with self._lock:
            self._records.insert(0, record)
            del self._records[self._history_limit:]
        return record.task_id

    def snapshot(self) -> tuple[TaskRecord, ...]:
        with self._lock:
            return tuple(
                TaskRecord(
                    task_id=record.task_id,
                    title=record.title,
                    status=record.status,
                    steps=[
                        TaskStep(step.title, step.skill_id, step.status, step.message)
                        for step in record.steps
                    ],
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                    message=record.message,
                    cancel_callback=record.cancel_callback,
                )
                for record in self._records
            )

    def _find(self, task_id: str) -> TaskRecord:
        for record in self._records:
            if record.task_id == task_id:
                return record
        raise KeyError(f"Görev bulunamadı: {task_id}")

    def start(self, task_id: str, message: str = "") -> None:
        with self._lock:
            record = self._find(task_id)
            if record.status not in {TaskStatus.QUEUED, TaskStatus.RUNNING}:
                raise ValueError(f"Başlatılamayan görev durumu: {record.status.value}")
            record.status = TaskStatus.RUNNING
            record.message = message
            record.updated_at = time.time()

    def update_step(
        self,
        task_id: str,
        step_index: int,
        status: StepStatus,
        message: str = "",
    ) -> None:
        with self._lock:
            record = self._find(task_id)
            if not 0 <= step_index < len(record.steps):
                raise IndexError("Görev adımı indeks aralığının dışında.")
            record.steps[step_index].status = status
            record.steps[step_index].message = message
            record.updated_at = time.time()

    def update_message(self, task_id: str, message: str) -> None:
        with self._lock:
            record = self._find(task_id)
            record.message = message
            record.updated_at = time.time()

    def finish(self, task_id: str, status: TaskStatus, message: str = "") -> None:
        if status not in {
            TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED,
        }:
            raise ValueError("Görev yalnızca son durumla tamamlanabilir.")
        with self._lock:
            record = self._find(task_id)
            record.status = status
            record.message = message
            record.cancel_callback = None
            record.updated_at = time.time()

    def request_cancel(self, task_id: str) -> bool:
        with self._lock:
            record = self._find(task_id)
            if record.status not in {TaskStatus.QUEUED, TaskStatus.RUNNING}:
                return False
            callback = record.cancel_callback
            if callback is None and record.status is TaskStatus.RUNNING:
                return False
            record.status = TaskStatus.CANCELLING
            record.message = "İptal isteği gönderildi."
            record.updated_at = time.time()
        if callback is not None:
            try:
                callback()
            except Exception:
                with self._lock:
                    record = self._find(task_id)
                    record.status = TaskStatus.RUNNING
                    record.message = "İptal başlatılamadı."
                    record.updated_at = time.time()
                raise
        else:
            self.finish(task_id, TaskStatus.CANCELLED, "Kullanıcı tarafından iptal edildi.")
        return True
