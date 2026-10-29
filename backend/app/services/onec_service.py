"""GET-only OData reader. No writes to 1C and no server-side boolean filters
(they proved unreliable); documents are filtered on the server only by date."""
import asyncio
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.onec import OneCRecord

ENTITIES = {
    "units": ("Catalog_КлассификаторЕдиницИзмерения", "Ref_Key,Description,Code,DeletionMark,НаименованиеПолное"),
    "kinds": ("Catalog_ВидыНоменклатуры", "Ref_Key,Description,Code,DeletionMark"),
    "items": ("Catalog_Номенклатура", "Ref_Key,Description,Code,DeletionMark,IsFolder,Parent_Key,БазоваяЕдиницаИзмерения_Key,ВидНоменклатуры_Key,ВесХлебов,Услуга"),
    "specs": ("Catalog_СпецификацииНоменклатуры", "Ref_Key,Description,Code,DeletionMark,IsFolder,Owner_Key,Количество,ИсходныеКомплектующие"),
    # Register rows have no Ref_Key; the snapshot keeps the current row per item.
    "main_specs": ("InformationRegister_ОсновныеСпецификацииНоменклатуры", "Period,Номенклатура_Key,СпецификацияНоменклатуры_Key"),
    "warehouses": ("Catalog_Склады", "Ref_Key,Description,Code,DeletionMark"),
}
ORDER_BY = {"main_specs": "Period,Номенклатура_Key"}
# Documents are read on demand for a period, not stored in the snapshot.
DOCUMENTS = {
    "reports": ("Document_ОтчетПроизводстваЗаСмену",
                "Ref_Key,Number,Date,Posted,DeletionMark,СкладСырья_Key,НеОтражатьВОтчетахПоСырью,Продукция", "Продукция"),
    "requisitions": ("Document_ТребованиеНакладная",
                     "Ref_Key,Number,Date,Posted,DeletionMark,Склад_Key,ДокументОснование,ДокументОснование_Type,Материалы", "Материалы"),
}


def is_number(value):
    return type(value) in (int, float)


def validate_row(kind, row):
    """Return the row's unique key; raise ValueError on unexpected 1C data."""
    if kind == "main_specs":
        if not isinstance(row["Period"], str):
            raise ValueError()
        uuid.UUID(row["СпецификацияНоменклатуры_Key"])
        return (row["Period"], uuid.UUID(row["Номенклатура_Key"]))
    ref = uuid.UUID(row["Ref_Key"])
    if ref.int == 0 or not isinstance(row["Description"], str) or type(row["DeletionMark"]) is not bool:
        raise ValueError()
    if kind in ("items", "specs") and type(row["IsFolder"]) is not bool:
        raise ValueError()
    if kind == "specs" and not row["IsFolder"]:
        uuid.UUID(row["Owner_Key"])
        if not is_number(row["Количество"]) or not isinstance(row["ИсходныеКомплектующие"], list):
            raise ValueError()
        for line in row["ИсходныеКомплектующие"]:
            uuid.UUID(line["Номенклатура_Key"])
            int(line["LineNumber"])
            if not is_number(line["Количество"]):
                raise ValueError()
    return ref


POSTING_FIELDS = "Period,Recorder,Recorder_Type,LineNumber,ExtDimensionCr1,ExtDimensionCr2,Сумма,КоличествоCr"


def validate_posting(row):
    if not isinstance(row["Recorder_Type"], str) or not is_number(row["Сумма"]):
        raise ValueError()
    if row["КоличествоCr"] is not None and not is_number(row["КоличествоCr"]):
        raise ValueError()
    return (uuid.UUID(row["Recorder"]), int(row["LineNumber"]))


def validate_document(kind, row):
    ref = uuid.UUID(row["Ref_Key"])
    if not isinstance(row["Date"], str) or not isinstance(row["Number"], str):
        raise ValueError()
    if type(row["Posted"]) is not bool or type(row["DeletionMark"]) is not bool:
        raise ValueError()
    if kind == "reports" and type(row["НеОтражатьВОтчетахПоСырью"]) is not bool:
        raise ValueError()
    uuid.UUID(row["СкладСырья_Key"] if kind == "reports" else row["Склад_Key"])
    lines = row[DOCUMENTS[kind][2]]
    if not isinstance(lines, list):
        raise ValueError()
    for line in lines:
        uuid.UUID(line["Номенклатура_Key"])
        if not is_number(line["Количество"]) or not is_number(line["Коэффициент"]):
            raise ValueError()
        uuid.UUID(line["Спецификация_Key"] if kind == "reports" else line["СчетБУ_Key"])
    return ref


def current_main_specs(rows, today):
    """The latest main specification per item whose period has started."""
    current = {}
    for row in sorted(rows, key=lambda r: r["Period"]):
        if row["Period"][:10] <= today:
            current[row["Номенклатура_Key"]] = row
    return list(current.values())


def row_ref(kind, row):
    return uuid.UUID(row["Номенклатура_Key"] if kind == "main_specs" else row["Ref_Key"])


class OneCError(Exception):
    pass


class OneCBusy(OneCError):
    pass


class OneCSessionLimit(OneCError):
    pass


SESSION_LIMIT_RETRY_DELAYS = (5, 15, 30)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward database credentials to another address.
        return None


class ODataReader:
    def __init__(self, url=None, user=None, password=None):
        self.url = (settings.onec_odata_url if url is None else url).rstrip("/") + "/"
        parsed = urllib.parse.urlsplit(self.url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
            raise OneCError("Настройте ONEC_ODATA_URL: адрес HTTP/HTTPS без пароля и параметров.")
        user = settings.onec_odata_user if user is None else user
        password = settings.onec_odata_password if password is None else password
        self.headers = {"Accept": "application/json", "Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")}
        self.source = hashlib.sha256(self.url.encode()).hexdigest()
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, entity, params, safe="/"):
        # The training version briefly refuses new sessions; retry before failing the whole sync.
        for delay in SESSION_LIMIT_RETRY_DELAYS:
            try:
                return self.request_once(entity, params, safe)
            except OneCSessionLimit:
                time.sleep(delay)
        return self.request_once(entity, params, safe)

    def request_once(self, entity, params, safe="/"):
        url = self.url + urllib.parse.quote(entity, safe=safe) + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        try:
            # Accounting register queries over a period take noticeably longer than catalog pages.
            with self.opener.open(urllib.request.Request(url, headers=self.headers, method="GET"), timeout=120) as response:
                raw = response.read(16 * 1024 * 1024 + 1)
                if len(raw) > 16 * 1024 * 1024:
                    raise OneCError("Ответ 1С превышает допустимый размер страницы.")
                return json.loads(raw.decode("utf-8-sig"))
        except urllib.error.HTTPError as exc:
            body = exc.read(8192).decode("utf-8-sig", errors="replace")
            if "предельное количество подключений" in body:
                raise OneCSessionLimit("1С отклонила подключение: достигнут лимит сеансов учебной версии.") from None
            if exc.code in (401, 403):
                raise OneCError("1С отказала в доступе. Проверьте учётную запись и права OData.") from None
            raise OneCError(f"1С вернула HTTP {exc.code}; синхронизация отменена.") from None
        except (OSError, ValueError) as exc:
            raise OneCError("Нет корректного ответа OData: проверьте доступность публикации 1С.") from exc

    def read_entity(self, kind):
        entity, fields = ENTITIES[kind]
        params = {"$select": fields, "$orderby": ORDER_BY.get(kind, "Ref_Key")}
        return self.read_all(entity, params, lambda row: validate_row(kind, row))

    def read_documents(self, kind, date_from, date_to):
        """Documents dated in [date_from, date_to), both naive local datetimes."""
        entity, fields, _ = DOCUMENTS[kind]
        params = {"$select": fields, "$orderby": "Ref_Key",
                  "$filter": f"Date ge datetime'{date_from:%Y-%m-%dT%H:%M:%S}' and Date lt datetime'{date_to:%Y-%m-%dT%H:%M:%S}'"}
        return self.read_all(entity, params, lambda row: validate_document(kind, row))

    def read_credit_postings(self, account_key, date_from, date_to, window=timedelta(days=2)):
        """Accounting postings crediting an account in [date_from, date_to), with subconto.

        The virtual table has no paging, so the period is read in short windows;
        its bounds are inclusive, hence the second subtracted and the dedup."""
        account = str(uuid.UUID(account_key))
        condition = "AccountCr_Key eq guid''" + account + "''"
        rows = {}
        start = date_from
        while start < date_to:
            end = min(start + window, date_to)
            function = (f"/RecordsWithExtDimensions(StartPeriod=datetime'{start:%Y-%m-%dT%H:%M:%S}',"
                        f"EndPeriod=datetime'{end - timedelta(seconds=1):%Y-%m-%dT%H:%M:%S}',Condition='{condition}')")
            data = self.request("AccountingRegister_Типовой" + function, {"$format": "json", "$select": POSTING_FIELDS},
                                safe="/(),=':")
            if not isinstance(data, dict) or not isinstance(data.get("value"), list):
                raise OneCError("Некорректный ответ регистра бухгалтерии.")
            for row in data["value"]:
                try:
                    rows[validate_posting(row)] = row
                except (ValueError, TypeError, KeyError, AttributeError):
                    raise OneCError("Некорректная проводка регистра бухгалтерии.") from None
            start = end
        return list(rows.values())

    def read_all(self, entity, params, validate):
        rows, seen = [], set()
        expected = None
        for offset in range(0, 100000, 200):
            data = self.request(entity, {"$format": "json", **params, "$top": 200, "$skip": offset, "$inlinecount": "allpages"})
            if not isinstance(data, dict) or not isinstance(data.get("value"), list):
                raise OneCError("Некорректная страница OData.")
            try:
                count = int(data["odata.count"])
            except (KeyError, ValueError, TypeError):
                raise OneCError("1С не вернула контрольное количество записей.") from None
            if expected is None:
                expected = count
            if count != expected or count < 0:
                raise OneCError("Данные 1С изменились во время чтения; повторите запрос.")
            batch = data["value"]
            for row in batch:
                try:
                    ref = validate(row)
                    if ref in seen:
                        raise ValueError()
                except (ValueError, TypeError, KeyError, AttributeError):
                    raise OneCError("Повторяющаяся ссылка или некорректные поля записи 1С.") from None
                seen.add(ref)
                rows.append(row)
            if len(rows) == expected:
                return rows
            if len(rows) > expected or len(batch) != 200:
                raise OneCError("Неполная выгрузка 1С; предыдущие данные сохранены.")
        raise OneCError("Превышен предел 100000 записей за один запрос.")


def summarize(records):
    counts = {}
    for kind, rows in records.items():
        counts[kind] = {"total": len(rows), "deleted": sum(bool(r.get("DeletionMark")) for r in rows),
                        "folders": sum(bool(r.get("IsFolder")) for r in rows)}
    units = {r["Ref_Key"] for r in records.get("units", []) if not r["DeletionMark"]}
    kinds = {r["Ref_Key"] for r in records.get("kinds", []) if not r["DeletionMark"]}
    active = [r for r in records.get("items", []) if not r["DeletionMark"] and not r["IsFolder"]]
    return {"counts": counts, "active_items": len(active),
            "items_without_active_unit": sum(r.get("БазоваяЕдиницаИзмерения_Key") not in units for r in active),
            "items_without_active_kind": sum(r.get("ВидНоменклатуры_Key") not in kinds for r in active)}


async def sync_references(db: AsyncSession, reader=None):
    reader = reader or ODataReader()
    # Across processes too: avoid overlapping requests to a single-session 1C.
    if not (await db.execute(text("SELECT pg_try_advisory_xact_lock(791463021)"))).scalar():
        raise OneCBusy("Синхронизация 1С уже выполняется.")
    try:
        records = {}
        for kind in ENTITIES:
            records[kind] = await asyncio.to_thread(reader.read_entity, kind)
        records["main_specs"] = current_main_specs(records["main_specs"], datetime.now().date().isoformat())
        # Replace only a completely fetched snapshot, in one transaction.
        await db.execute(delete(OneCRecord).where(OneCRecord.source == reader.source))
        now = datetime.now(timezone.utc)
        for kind, rows in records.items():
            db.add_all([OneCRecord(source=reader.source, entity=kind, ref=row_ref(kind, row), data=row, synced_at=now) for row in rows])
        await db.commit()
        return {"synced_at": now.isoformat(), **summarize(records)}
    except BaseException:
        await db.rollback()
        raise


async def reference_status(db):
    if not settings.onec_odata_url:
        return {"configured": False, "synced_at": None, "counts": {}}
    reader = ODataReader()
    records = {kind: [] for kind in ENTITIES}
    rows = (await db.execute(select(OneCRecord).where(OneCRecord.source == reader.source))).scalars().all()
    for row in rows:
        records[row.entity].append(row.data)
    return {"configured": True, "synced_at": max((r.synced_at for r in rows), default=None), **summarize(records)}
