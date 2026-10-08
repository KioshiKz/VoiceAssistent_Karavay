from collections.abc import Iterable

from app.models.order import OrderLine


def effective_order_lines(lines: Iterable[OrderLine]) -> list[OrderLine]:
    """Apply the emergency overlay without mutating the source application.

    Active emergency additions and replacements are always returned before the
    unaffected source lines. Remove markers only hide their source line.
    """
    all_lines = list(lines)
    overlays = [line for line in all_lines if line.emergency_schedule_id is not None]
    active_overlays = [line for line in overlays if line.emergency_active]
    source_overlays = {
        line.emergency_source_line_id: line
        for line in sorted(active_overlays, key=lambda item: item.created_at)
        if line.emergency_source_line_id is not None
    }

    emergency_lines = [
        line
        for line in active_overlays
        if line.emergency_action in {"add", "replace"} and line.status != "cancelled"
    ]
    source_lines = [
        line
        for line in all_lines
        if line.emergency_schedule_id is None
        and line.id not in source_overlays
    ]
    return sorted(emergency_lines, key=lambda item: (item.due_time, item.created_at)) + sorted(
        source_lines, key=lambda item: (item.due_time, item.created_at)
    )
