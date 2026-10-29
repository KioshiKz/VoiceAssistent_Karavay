"""Raw material write-off reconciliation: 1C production norm versus 1C requisitions.

Norm: posted shift production reports x the specification on each line
(defective output included, it consumed materials too). Fact: posted
requisitions by the raw material warehouse, split by what they were based on.
Read-only: documents are fetched from 1C for the period, nothing is stored.
"""
import asyncio
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.onec_import_service import clean_name, load_snapshot
from app.services.onec_service import OneCBusy, OneCError

MAX_DAYS = 93
# Requisitions are usually made right after their report; look a little past
# the period so a report at its end is not flagged as missing a requisition.
LINK_GRACE = timedelta(days=7)
REPORT_BASE = "Document_ОтчетПроизводстваЗаСмену"
ACT_BASE = "Document_АктПриемаПередачи"
EMPTY_REF = "00000000-0000-0000-0000-000000000000"


class OneCReconcileError(OneCError):
    pass


def number(value):
    return Decimal(str(value))


def out(value):
    return float(round(value, 3))


def deviates(norm, fact):
    return abs(fact - norm) > max(Decimal("0.001"), abs(norm) / 100)


def source_of(requisition):
    base_type = requisition["ДокументОснование_Type"].rsplit(".", 1)[-1]
    if base_type == REPORT_BASE:
        return "report"
    if base_type == ACT_BASE:
        return "act"
    return "other"


def report_norm(report, specs, missing):
    """Material -> quantity for one report; lines without a spec go to `missing`."""
    norm = {}
    for line in report["Продукция"]:
        spec = specs.get(line["Спецификация_Key"])
        if spec is None or spec.get("IsFolder") or not spec["Количество"]:
            missing.append((report, line))
            continue
        share = number(line["Количество"]) * number(line["Коэффициент"]) / number(spec["Количество"])
        for component in spec["ИсходныеКомплектующие"]:
            key = component["Номенклатура_Key"]
            norm[key] = norm.get(key, Decimal(0)) + number(component["Количество"]) * share
    return norm


def requisition_fact(requisition):
    fact = {}
    for line in requisition["Материалы"]:
        key = line["Номенклатура_Key"]
        fact[key] = fact.get(key, Decimal(0)) + number(line["Количество"]) * number(line["Коэффициент"])
    return fact


def reconcile(reports, requisitions, records, period_end):
    """Pure part. `period_end` is the exclusive end; later requisitions only link reports."""
    items = {r["Ref_Key"]: r for r in records.get("items", [])}
    units = {r["Ref_Key"]: r["Description"].strip() for r in records.get("units", [])}
    specs = {r["Ref_Key"]: r for r in records.get("specs", [])}
    warehouses = {r["Ref_Key"]: clean_name(r["Description"]) for r in records.get("warehouses", [])}
    end = period_end.isoformat()

    def item_name(ref):
        return clean_name(items[ref]["Description"]) if ref in items else f"Неизвестная позиция {ref[:8]}"

    def unit_name(ref):
        return units.get(items.get(ref, {}).get("БазоваяЕдиницаИзмерения_Key"), "")

    def warehouse_name(ref):
        return warehouses.get(ref, "Склад не указан" if ref == EMPTY_REF else f"Склад {ref[:8]}")

    reports = [r for r in reports if r["Posted"] and not r["DeletionMark"]]
    requisitions = [r for r in requisitions if r["Posted"] and not r["DeletionMark"]]
    linked = {}
    for requisition in requisitions:
        if source_of(requisition) == "report":
            linked.setdefault(requisition["ДокументОснование"], []).append(requisition)

    rows, missing_spec, without_requisition, deviations = {}, [], [], []

    def row(warehouse, material):
        key = (warehouse, material)
        if key not in rows:
            rows[key] = {"norm": Decimal(0), "report": Decimal(0), "act": Decimal(0), "other": Decimal(0)}
        return rows[key]

    skipped_reports = 0
    for report in reports:
        if report["НеОтражатьВОтчетахПоСырью"]:
            skipped_reports += 1
            continue
        norm = report_norm(report, specs, missing_spec)
        for material, quantity in norm.items():
            row(report["СкладСырья_Key"], material)["norm"] += quantity
        own = linked.get(report["Ref_Key"], [])
        if not own:
            without_requisition.append(report)
            continue
        fact = {}
        for requisition in own:
            for material, quantity in requisition_fact(requisition).items():
                fact[material] = fact.get(material, Decimal(0)) + quantity
        differing = [m for m in set(norm) | set(fact) if deviates(norm.get(m, Decimal(0)), fact.get(m, Decimal(0)))]
        if differing:
            differing.sort(key=lambda m: -abs(fact.get(m, Decimal(0)) - norm.get(m, Decimal(0))) / max(norm.get(m, Decimal(0)), Decimal("0.001")))
            deviations.append({
                "number": report["Number"].strip(),
                "date": report["Date"],
                "warehouse": warehouse_name(report["СкладСырья_Key"]),
                "requisitions": [r["Number"].strip() for r in own],
                "materials_differing": len(differing),
                "top": [{"material": item_name(m), "unit": unit_name(m), "norm": out(norm.get(m, Decimal(0))),
                         "fact": out(fact.get(m, Decimal(0)))} for m in differing[:3]],
            })

    for requisition in requisitions:
        if requisition["Date"] >= end:
            continue
        for material, quantity in requisition_fact(requisition).items():
            row(requisition["Склад_Key"], material)[source_of(requisition)] += quantity

    result_rows = []
    for (warehouse, material), values in rows.items():
        fact = values["report"] + values["act"] + values["other"]
        diff = fact - values["norm"]
        result_rows.append({
            "warehouse": warehouse_name(warehouse),
            "material": item_name(material),
            "code": items.get(material, {}).get("Code", "").strip(),
            "unit": unit_name(material),
            "norm": out(values["norm"]),
            "fact": out(fact),
            "fact_by_report": out(values["report"]),
            "fact_by_act": out(values["act"]),
            "fact_other": out(values["other"]),
            "diff": out(diff),
            "diff_pct": out(diff / values["norm"] * 100) if values["norm"] else None,
        })
    result_rows.sort(key=lambda r: (r["warehouse"], r["material"]))
    deviations.sort(key=lambda d: (-d["materials_differing"], d["date"]))

    return {
        "reports": len(reports),
        "reports_not_reflected": skipped_reports,
        "requisitions": sum(1 for r in requisitions if r["Date"] < end),
        "rows": result_rows,
        "reports_without_requisition": [
            {"number": r["Number"].strip(), "date": r["Date"], "warehouse": warehouse_name(r["СкладСырья_Key"]),
             "products": len(r["Продукция"])}
            for r in sorted(without_requisition, key=lambda r: r["Date"])
        ],
        "lines_without_spec": [
            {"number": r["Number"].strip(), "date": r["Date"], "product": item_name(line["Номенклатура_Key"]),
             "quantity": out(number(line["Количество"]))}
            for r, line in missing_spec
        ],
        "report_deviations_total": len(deviations),
        "report_deviations": deviations[:100],
    }


async def run_reconciliation(db: AsyncSession, reader, date_from: date, date_to: date):
    if date_to < date_from or (date_to - date_from).days >= MAX_DAYS:
        raise OneCReconcileError(f"Укажите период не длиннее {MAX_DAYS} дней.")
    # Shares the sync lock: the training 1C allows very few sessions.
    if not (await db.execute(text("SELECT pg_try_advisory_xact_lock(791463021)"))).scalar():
        raise OneCBusy("Сейчас уже идёт обмен с 1С; повторите позже.")
    try:
        records = await load_snapshot(db, reader.source)
        if not records.get("specs"):
            raise OneCReconcileError("В загруженных данных нет спецификаций. Сначала синхронизируйте 1С.")
        start = datetime.combine(date_from, time.min)
        end = datetime.combine(date_to + timedelta(days=1), time.min)
        reports = await asyncio.to_thread(reader.read_documents, "reports", start, end)
        requisitions = await asyncio.to_thread(reader.read_documents, "requisitions", start, end + LINK_GRACE)
        return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
                **reconcile(reports, requisitions, records, end)}
    finally:
        await db.rollback()
