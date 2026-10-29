"""Order and yield quantities in a product's unit: whole pieces or kilograms."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from fastapi import HTTPException


def normalize_quantity(value, unit: str | None) -> float:
    """Round to grams; piece products must be whole (unit None: not matched yet). Raises 422 otherwise."""
    try:
        quantity = Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise HTTPException(422, detail="Укажите количество числом.") from None
    if quantity <= 0:
        raise HTTPException(422, detail="Количество должно быть больше нуля.")
    if unit == "pcs" and quantity != quantity.to_integral_value():
        raise HTTPException(422, detail="Для штучной продукции количество должно быть целым.")
    return float(quantity)

