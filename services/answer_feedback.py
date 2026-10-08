"""Cautious evidence labels for assistant answers."""
from __future__ import annotations

from services.atlas_memory import answer_feedback


def format_answer_feedback(query: str, local_sources_shared: bool) -> str:
    if not local_sources_shared:
        return (
            "Kaynak durumu: yanıt yerel belgelerle doğrulanmadı. "
            "Önemli bilgileri ayrıca kontrol edin."
        )
    return answer_feedback(query)
