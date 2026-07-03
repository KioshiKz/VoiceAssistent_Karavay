import datetime
import io
from dataclasses import dataclass

import openpyxl
from fastapi import HTTPException


@dataclass
class ParsedLine:
    row_group_index: int
    product_name_raw: str
    quantity: int
    due_time: datetime.time


def _parse_time(raw) -> datetime.time:
    if isinstance(raw, datetime.time):
        return raw
    if isinstance(raw, datetime.datetime):
        return raw.time()
    try:
        return datetime.datetime.strptime(str(raw).strip(), "%H:%M").time()
    except ValueError:
        raise HTTPException(400, detail=f"invalid_time_value: {raw!r}")


def parse_order_file(file_bytes: bytes) -> list[ParsedLine]:
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception:
        raise HTTPException(400, detail="invalid_xlsx_file")

    ws = wb.active
    values = [row[0].value for row in ws.iter_rows(min_col=1, max_col=1) if row[0].value is not None]

    if len(values) == 0:
        raise HTTPException(400, detail="empty_file")
    if len(values) % 3 != 0:
        raise HTTPException(400, detail="row_count_not_multiple_of_3")

    lines: list[ParsedLine] = []
    for i in range(0, len(values), 3):
        name_raw, qty_raw, time_raw = values[i], values[i + 1], values[i + 2]
        try:
            quantity = int(qty_raw)
        except (TypeError, ValueError):
            raise HTTPException(400, detail=f"invalid_quantity_at_row_group_{i // 3}: {qty_raw!r}")
        if quantity <= 0:
            raise HTTPException(400, detail=f"quantity_must_be_positive_at_row_group_{i // 3}")

        lines.append(
            ParsedLine(
                row_group_index=i // 3,
                product_name_raw=str(name_raw).strip(),
                quantity=quantity,
                due_time=_parse_time(time_raw),
            )
        )
    return lines
