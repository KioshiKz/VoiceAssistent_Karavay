"""Canonical storage units: weight=grams, volume=milliliters, time=seconds,
temperature=degrees Celsius, count=pieces. Canonical quantities are Decimal so
small weights such as 1.7 g are not rounded away."""

from decimal import Decimal, ROUND_HALF_UP


DISPLAY_UNITS: dict[str, list[tuple[str, Decimal]]] = {
    "weight": [("g", Decimal("1")), ("kg", Decimal("1000")), ("t", Decimal("1000000"))],
    "volume": [("ml", Decimal("1")), ("l", Decimal("1000"))],
    "time": [("sec", Decimal("1")), ("min", Decimal("60")), ("hour", Decimal("3600"))],
    "temperature": [("celsius", Decimal("1"))],
    "count": [("pcs", Decimal("1"))],
}


def _decimal(value: Decimal | float | int | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _trim(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.001")).normalize()
    if normalized == normalized.to_integral():
        return format(normalized.to_integral(), "f")
    return format(normalized, "f")


def to_canonical(measure_type: str, value: float, unit: str) -> Decimal:
    units = dict(DISPLAY_UNITS[measure_type])
    if unit not in units:
        raise ValueError(f"unknown unit '{unit}' for measure_type '{measure_type}'")
    return (_decimal(value) * units[unit]).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def round_half_up(value: float) -> int:
    import math

    return math.floor(value + 0.5)


def quantize_quantity(value: Decimal | float | int | str) -> Decimal:
    return _decimal(value).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def format_compound(value_canonical: Decimal | float | int, measure_type: str | None) -> str:
    value = quantize_quantity(value_canonical)
    if measure_type == "weight":
        kg = int(value // Decimal("1000"))
        g = value - Decimal(kg * 1000)
        return f"{kg} кг {_trim(g)} г" if kg else f"{_trim(g)} г"
    if measure_type == "volume":
        liters = int(value // Decimal("1000"))
        ml = value - Decimal(liters * 1000)
        return f"{liters} л {_trim(ml)} мл" if liters else f"{_trim(ml)} мл"
    if measure_type == "time":
        hours = int(value // Decimal("3600"))
        remainder = value - Decimal(hours * 3600)
        minutes = int(remainder // Decimal("60"))
        seconds = remainder - Decimal(minutes * 60)
        parts = [
            f"{hours} ч" if hours else "",
            f"{minutes} мин" if minutes else "",
            f"{_trim(seconds)} сек" if seconds else "",
        ]
        return " ".join(part for part in parts if part) or "0 сек"
    if measure_type == "temperature":
        return f"{_trim(value)} °C"
    if measure_type == "count":
        return f"{_trim(value)} шт"
    raise ValueError(f"unknown measure_type '{measure_type}'")
