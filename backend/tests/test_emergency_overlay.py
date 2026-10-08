import datetime
import uuid
from types import SimpleNamespace

from app.services.emergency_service import effective_order_lines


def _line(
    name: str,
    *,
    due: str,
    schedule: uuid.UUID | None = None,
    source: uuid.UUID | None = None,
    action: str | None = None,
    active: bool = False,
    status: str = "pending",
):
    hour, minute = map(int, due.split(":"))
    return SimpleNamespace(
        id=uuid.uuid4(),
        product_name_raw=name,
        due_time=datetime.time(hour, minute),
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        emergency_schedule_id=schedule,
        emergency_source_line_id=source,
        emergency_action=action,
        emergency_active=active,
        status=status,
    )


def test_emergency_additions_and_replacements_are_a_priority_overlay():
    schedule = uuid.uuid4()
    source_replaced = _line("Булочка", due="08:00")
    source_untouched = _line("Хлеб", due="07:00")
    replacement = _line(
        "Булочка",
        due="09:00",
        schedule=schedule,
        source=source_replaced.id,
        action="replace",
        active=True,
    )
    addition = _line("Кекс", due="10:00", schedule=schedule, action="add", active=True)

    result = effective_order_lines([source_replaced, source_untouched, replacement, addition])

    assert [line.product_name_raw for line in result] == ["Булочка", "Кекс", "Хлеб"]
    assert source_replaced not in result


def test_remove_marker_hides_source_and_inactive_marker_does_not():
    schedule = uuid.uuid4()
    hidden = _line("Батон", due="08:00")
    restored = _line("Багет", due="09:00")
    remove = _line(
        "Батон",
        due="08:00",
        schedule=schedule,
        source=hidden.id,
        action="remove",
        active=True,
    )
    inactive_replace = _line(
        "Багет",
        due="09:00",
        schedule=schedule,
        source=restored.id,
        action="replace",
        active=False,
    )

    result = effective_order_lines([hidden, restored, remove, inactive_replace])

    assert hidden not in result
    assert restored in result
    assert remove not in result
    assert inactive_replace not in result
