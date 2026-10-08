"""Small helpers for conservative low-resource device detection."""
from __future__ import annotations

LOW_RESOURCE_MAX_LOGICAL_CPUS = 4
LOW_RESOURCE_MAX_MEMORY_BYTES = 4 * 1024 * 1024 * 1024


def detect_low_resource_mode(
    logical_cpu_count: int | None,
    memory_bytes: int | None,
) -> bool:
    """Detect modest hardware without treating unknown values as low-end."""
    cpu_is_limited = (
        logical_cpu_count is not None
        and 0 < logical_cpu_count <= LOW_RESOURCE_MAX_LOGICAL_CPUS
    )
    memory_is_limited = (
        memory_bytes is not None
        and 0 < memory_bytes <= LOW_RESOURCE_MAX_MEMORY_BYTES
    )
    return cpu_is_limited or memory_is_limited
