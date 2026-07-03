"""Canonical storage units: weight=grams, volume=milliliters, time=seconds,
temperature=degrees Celsius (one decimal). All arithmetic (multipliers, sums)
must happen on the canonical integer value; display formatting is a pure,
derived function and is never the source of truth."""

DISPLAY_UNITS: dict[str, list[tuple[str, int]]] = {
    "weight": [("g", 1), ("kg", 1000), ("t", 1_000_000)],
    "volume": [("ml", 1), ("l", 1000)],
    "time": [("sec", 1), ("min", 60), ("hour", 3600)],
    "temperature": [("celsius", 1)],
}


def to_canonical(measure_type: str, value: float, unit: str) -> int:
    units = dict(DISPLAY_UNITS[measure_type])
    if unit not in units:
        raise ValueError(f"unknown unit '{unit}' for measure_type '{measure_type}'")
    return round(value * units[unit])


def round_half_up(value: float) -> int:
    import math

    return math.floor(value + 0.5)


def format_compound(value_canonical: int, measure_type: str) -> str:
    if measure_type == "weight":
        kg, g = divmod(value_canonical, 1000)
        return f"{kg} кг {g} г" if kg else f"{g} г"
    if measure_type == "volume":
        l, ml = divmod(value_canonical, 1000)
        return f"{l} л {ml} мл" if l else f"{ml} мл"
    if measure_type == "time":
        h, rem = divmod(value_canonical, 3600)
        m, s = divmod(rem, 60)
        parts = [p for p in [f"{h} ч" if h else "", f"{m} мин" if m else "", f"{s} сек" if s else ""] if p]
        return " ".join(parts) if parts else "0 сек"
    if measure_type == "temperature":
        return f"{value_canonical / 10:.1f} °C"
    raise ValueError(f"unknown measure_type '{measure_type}'")
