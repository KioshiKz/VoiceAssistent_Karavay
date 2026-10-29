import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { ConsoleShell } from "../components/ConsoleShell";
import { apiErrorMessage } from "../utils/apiError";

type Kind = "items" | "units" | "kinds";
type Status = {
  configured: boolean;
  synced_at: string | null;
  counts: Partial<Record<Kind | "specs" | "main_specs", { total: number; deleted: number; folders: number }>>;
  active_items?: number;
  items_without_active_unit?: number;
  items_without_active_kind?: number;
};
type RecordRow = { Ref_Key: string; Description: string; Code: string; DeletionMark: boolean; IsFolder?: boolean };
type Page = { total: number; items: RecordRow[] };
type Workshop = { id: string; name: string };
type Reason = { reason: string; count: number; examples: string[] };
type ImportReport = {
  dry_run: boolean;
  candidates: number;
  products_created: number;
  products_updated: number;
  products_unchanged: number;
  products_reactivated: number;
  products_deactivated: number;
  ingredients_created: number;
  ingredients_updated: number;
  steps_written: number;
  folders_created: number;
  skipped: Reason[];
  skipped_lines: Reason[];
  warnings: Reason[];
  conflicts: Reason[];
};
const labels: Record<Kind, string> = { items: "Номенклатура", units: "Единицы измерения", kinds: "Виды номенклатуры" };

export function OneCIntegration() {
  const [status, setStatus] = useState<Status | null>(null);
  const [kind, setKind] = useState<Kind>("items");
  const [page, setPage] = useState(0);
  const [data, setData] = useState<Page | null>(null);
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [workshops, setWorkshops] = useState<Workshop[]>([]);
  const [workshopId, setWorkshopId] = useState("");
  const [report, setReport] = useState<ImportReport | null>(null);
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    apiClient.get<Status>("/integrations/1c/status", { signal: controller.signal })
      .then(({ data }) => setStatus(data))
      .catch((err: unknown) => { if (!controller.signal.aborted) setError(apiErrorMessage(err, "Не удалось получить состояние подключения.")); });
    return () => controller.abort();
  }, [revision]);

  useEffect(() => {
    if (!status?.configured) return;
    const controller = new AbortController();
    setLoading(true);
    setData(null);
    apiClient.get<Page>(`/integrations/1c/records/${kind}`, { params: { offset: page * 50, limit: 50 }, signal: controller.signal })
      .then(({ data }) => setData(data))
      .catch((err: unknown) => { if (!controller.signal.aborted) setError(apiErrorMessage(err, "Не удалось загрузить справочник.")); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [kind, page, revision, status?.configured]);

  useEffect(() => {
    if (!status?.configured) return;
    const controller = new AbortController();
    apiClient.get<Workshop[]>("/integrations/1c/import/workshops", { signal: controller.signal })
      .then(({ data }) => {
        setWorkshops(data);
        setWorkshopId((current) => current || (data.find((w) => w.name === "Производство") ?? data[0])?.id || "");
      })
      .catch((err: unknown) => { if (!controller.signal.aborted) setError(apiErrorMessage(err, "Не удалось получить список цехов.")); });
    return () => controller.abort();
  }, [status?.configured]);

  async function runImport(dryRun: boolean) {
    if (!dryRun && !window.confirm("Перенести рецептуры из 1С в техкарты выбранного цеха?")) return;
    setImporting(true);
    setError("");
    try {
      const { data } = await apiClient.post<ImportReport>("/integrations/1c/import", { workshop_id: workshopId, dry_run: dryRun }, { timeout: 300000 });
      setReport(data);
    } catch (err) {
      setError(apiErrorMessage(err, "Перенос не выполнен. Данные приложения не изменены."));
    } finally {
      setImporting(false);
    }
  }

  async function sync() {
    setBusy(true);
    setError("");
    try {
      // A complete snapshot requires many sequential requests to 1C.
      await apiClient.post("/integrations/1c/sync", null, { timeout: 600000 });
      setPage(0);
      setRevision((value) => value + 1);
    } catch (err) {
      setError(apiErrorMessage(err, "Синхронизация не завершена. Последняя успешная загрузка сохранена."));
    } finally {
      setBusy(false);
    }
  }

  return <ConsoleShell title="Данные 1С" subtitle="Первый этап: номенклатура и единицы измерения" actions={
    <button type="button" disabled={busy || !status?.configured} onClick={() => void sync()}>{busy ? "Загрузка из 1С…" : "Синхронизировать"}</button>
  }>
    <section className="editor-card">
      <p>Здесь показаны справочники, полученные из 1С. Перенос выбранных позиций и рецептур в рабочие техкарты будет следующим этапом.</p>
      <p>{status ? (status.configured ? `Последняя успешная загрузка: ${status.synced_at ? new Date(status.synced_at).toLocaleString("ru-RU") : "ещё не выполнялась"}` : "Подключение 1С ещё не настроено.") : "Проверка подключения…"}</p>
      {busy && <p role="status">Получаем справочники. Это может занять несколько минут. До завершения отображаются данные предыдущей загрузки.</p>}
      {error && <p className="error-text" role="alert">{error}</p>}
    </section>
    {status?.configured && <>
      <section className="statistics-summary">
        {(Object.keys(labels) as Kind[]).map((key) => <article key={key}><small>{labels[key]}</small><strong>{status.counts[key]?.total ?? 0}</strong></article>)}
        <article><small>Действующие позиции без папок</small><strong>{status.active_items ?? 0}</strong></article>
        <article><small>Основные спецификации</small><strong>{status.counts.main_specs?.total ?? 0}</strong></article>
      </section>
      {((status.items_without_active_unit ?? 0) > 0 || (status.items_without_active_kind ?? 0) > 0) && <section className="editor-card">
        <h2>Требуют проверки перед переносом</h2>
        <p>Без действующей единицы измерения: {status.items_without_active_unit ?? 0}. Без действующего вида номенклатуры: {status.items_without_active_kind ?? 0}.</p>
      </section>}
      <section className="editor-card">
        <h2>Перенос рецептур в техкарты</h2>
        <p>Переносятся действующие основные спецификации с выходом в штуках. Продукция и сырьё попадают в папку «1С» выбранного цеха с группами как в 1С. Повторный перенос обновляет только то, что изменилось в 1С; рецептуры, изменённые вручную в приложении, не перезаписываются.</p>
        <label>Цех <select value={workshopId} onChange={(event) => { setWorkshopId(event.target.value); setReport(null); }}>
          {workshops.map((w) => <option value={w.id} key={w.id}>{w.name}</option>)}
        </select></label>
        <div className="statistics-pagination">
          <button type="button" disabled={importing || busy || !workshopId} onClick={() => void runImport(true)}>{importing ? "Проверка…" : "Проверить перенос"}</button>
          <button type="button" disabled={importing || busy || !workshopId || !report?.dry_run} onClick={() => void runImport(false)}>Перенести</button>
        </div>
        {report && <ImportSummary report={report} />}
      </section>
      <section className="editor-card">
        <label>Справочник <select value={kind} onChange={(event) => { setKind(event.target.value as Kind); setPage(0); setError(""); }}>
          {(Object.keys(labels) as Kind[]).map((key) => <option value={key} key={key}>{labels[key]}</option>)}
        </select></label>
        <p>Помеченные на удаление записи сохранены для сверки и отмечены в списке.</p>
        {loading ? <p role="status">Загрузка списка…</p> : data && <>
          <div className="order-table-scroll"><table className="order-table">
            <thead><tr><th>Код</th><th>Наименование</th><th>Состояние</th></tr></thead>
            <tbody>{data.items.map((row) => <tr key={row.Ref_Key}><td>{row.Code.trim()}</td><td>{row.Description}</td><td>{row.DeletionMark ? "Помечено на удаление" : row.IsFolder ? "Папка" : "Действует"}</td></tr>)}</tbody>
          </table></div>
          {!data.total && <p>Записей пока нет.</p>}
          <div className="statistics-pagination">
            <button type="button" disabled={!page} onClick={() => setPage((value) => value - 1)}>Назад</button>
            <span>Страница {page + 1} из {Math.max(1, Math.ceil(data.total / 50))} · Всего {data.total}</span>
            <button type="button" disabled={(page + 1) * 50 >= data.total} onClick={() => setPage((value) => value + 1)}>Дальше</button>
          </div>
        </>}
      </section>
    </>}
  </ConsoleShell>;
}

function ReasonList({ title, reasons }: { title: string; reasons: Reason[] }) {
  if (!reasons.length) return null;
  return <>
    <h3>{title}</h3>
    <ul>{reasons.map((r) => <li key={r.reason}>{r.reason}: {r.count}{r.examples.length > 0 && <small> (например: {r.examples.join("; ")})</small>}</li>)}</ul>
  </>;
}

function ImportSummary({ report }: { report: ImportReport }) {
  return <div role="status">
    <p><strong>{report.dry_run ? "Предпросмотр: изменения не сохранены." : "Перенос выполнен."}</strong></p>
    <p>
      Рецептур к переносу: {report.candidates}. Новых продуктов: {report.products_created}, обновлено: {report.products_updated},
      без изменений: {report.products_unchanged}, снова активно: {report.products_reactivated}, скрыто (нет в 1С): {report.products_deactivated}.
      Новых ингредиентов: {report.ingredients_created}, переименовано: {report.ingredients_updated}. Шагов рецептур: {report.steps_written}. Новых папок: {report.folders_created}.
    </p>
    <ReasonList title="Не перенесено: изменено вручную или несовместимо" reasons={report.conflicts} />
    <ReasonList title="Пропущенные спецификации" reasons={report.skipped} />
    <ReasonList title="Пропущенные строки состава" reasons={report.skipped_lines} />
    <ReasonList title="Предупреждения" reasons={report.warnings} />
  </div>;
}
