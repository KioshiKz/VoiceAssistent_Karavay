import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronRight, RefreshCw } from "lucide-react";
import { foldersApi, statisticsApi } from "../api/endpoints";
import type { FolderOut, StatisticsOut } from "../api/types";
import { ConsoleShell } from "../components/ConsoleShell";
import { HISTORY_LABELS } from "../utils/orderHistory";

const EVENT_LABELS: Record<string, string> = {
  ...HISTORY_LABELS,
  emergency_schedule_started: "Включён экстренный режим",
  emergency_item_added: "Экстренно добавлена продукция",
  emergency_quantity_replaced: "Экстренно изменено количество",
  emergency_item_removed: "Позиция исключена экстренно",
  emergency_item_updated: "Экстренная позиция изменена",
  emergency_item_restored: "Экстренное изменение отменено",
};

export function Statistics() {
  const pageSize = 25;
  const [data, setData] = useState<StatisticsOut | null>(null);
  const [workshops, setWorkshops] = useState<FolderOut[]>([]);
  const [filters, setFilters] = useState({ date_from: "", date_to: "", workshop_folder_id: "", event_type: "" });
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await statisticsApi.get({
        date_from: filters.date_from || undefined,
        date_to: filters.date_to || undefined,
        workshop_folder_id: filters.workshop_folder_id || undefined,
        event_type: filters.event_type || undefined,
        limit: pageSize,
        offset: page * pageSize,
      }));
    } catch {
      setError("Не удалось загрузить статистику.");
    } finally {
      setLoading(false);
    }
  }, [filters.date_from, filters.date_to, filters.event_type, filters.workshop_folder_id, page]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    foldersApi.tree()
      .then((items) => setWorkshops(items.filter((item) => item.parent_id === null).sort((a, b) => a.name.localeCompare(b.name, "ru"))))
      .catch(() => setWorkshops([]));
  }, []);

  function updateFilter(key: keyof typeof filters, value: string) {
    setPage(0);
    setFilters((current) => ({ ...current, [key]: value }));
  }

  function toggle(id: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <ConsoleShell
      title="Статистика и полный журнал"
      subtitle="Все заявки, позиции, исполнение и экстренные изменения с данными до и после."
      actions={<button type="button" onClick={() => void reload()} disabled={loading}><RefreshCw size={17} /> Обновить</button>}
    >
      <section className="statistics-filters">
        <label>С даты<input type="date" value={filters.date_from} onChange={(event) => updateFilter("date_from", event.target.value)} /></label>
        <label>По дату<input type="date" value={filters.date_to} onChange={(event) => updateFilter("date_to", event.target.value)} /></label>
        <label>Цех<select value={filters.workshop_folder_id} onChange={(event) => updateFilter("workshop_folder_id", event.target.value)}>
          <option value="">Все цеха</option>
          {workshops.map((workshop) => <option key={workshop.id} value={workshop.id}>{workshop.name}</option>)}
        </select></label>
        <label>Событие<select value={filters.event_type} onChange={(event) => updateFilter("event_type", event.target.value)}>
          <option value="">Все события</option>
          {Object.entries(EVENT_LABELS).sort((a, b) => a[1].localeCompare(b[1], "ru")).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
      </section>

      {error && <p className="error-text">{error}</p>}
      {data && (
        <div className="statistics-page">
          <section className="statistics-summary">
            <article><small>Заявок</small><strong>{data.summary.orders}</strong></article>
            <article><small>Всего позиций</small><strong>{data.summary.positions}</strong></article>
            <article><small>Выполнено</small><strong>{data.summary.completed}</strong></article>
            <article><small>В работе</small><strong>{data.summary.in_progress}</strong></article>
            <article><small>Ожидает</small><strong>{data.summary.pending}</strong></article>
            <article><small>Экстренных расписаний</small><strong>{data.summary.emergency_schedules}</strong></article>
            <article className="emergency-stat"><small>Экстренных изменений</small><strong>{data.summary.emergency_changes}</strong></article>
          </section>

          <section className="editor-card statistics-products">
            <div className="pane-heading"><div><p className="eyebrow">Продукция</p><h2>Все позиции за период</h2></div></div>
            <div className="order-table-scroll"><table className="order-table"><thead><tr><th>Продукция</th><th>Позиций</th><th>Количество</th><th>Готово</th><th>Отменено</th><th>Экстренных</th></tr></thead>
              <tbody>{data.products.map((row) => <tr key={row.product_name}><td><strong>{row.product_name}</strong></td><td>{row.positions}</td><td>{row.total_quantity}</td><td>{row.completed}</td><td>{row.cancelled}</td><td>{row.emergency_positions}</td></tr>)}</tbody>
            </table></div>
          </section>

          <section className="editor-card statistics-log">
            <div className="pane-heading"><div><p className="eyebrow">Аудит</p><h2>Полный журнал · {data.logs_total} записей</h2></div></div>
            {data.logs.length === 0 ? <div className="empty-state">За выбранный период событий нет.</div> : (
              <div className="audit-list">{data.logs.map((log) => {
                const logKey = `${log.source}-${log.id}`;
                const open = expanded.has(logKey);
                return <article key={`${log.source}-${log.id}`} className={log.source === "emergency" ? "emergency-log" : ""}>
                  <button
                    type="button"
                    className="audit-heading"
                    aria-expanded={open}
                    aria-controls={`audit-details-${logKey}`}
                    onClick={() => toggle(logKey)}
                  >
                    {open ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                    <span><strong>{EVENT_LABELS[log.event_type] ?? log.event_type}</strong><small>{log.product_name_raw ?? "Заявка"} · {log.actor_name ?? "система"} · {new Date(log.created_at).toLocaleString("ru-RU")}</small></span>
                    {log.source === "emergency" && <b>ЭКСТРЕННО</b>}
                  </button>
                  {open && <div className="audit-details" id={`audit-details-${logKey}`}>
                    {log.note && <p>{log.note}</p>}
                    <div><section><strong>До</strong><pre>{JSON.stringify(log.old_value, null, 2) || "—"}</pre></section><section><strong>После</strong><pre>{JSON.stringify(log.new_value, null, 2) || "—"}</pre></section></div>
                    <small>Заявка: {log.order_id ?? "удалена"} · строка: {log.order_line_id ?? "—"}</small>
                  </div>}
                </article>;
              })}</div>
            )}
            {data.logs_total > pageSize && (
              <div className="statistics-pagination">
                <button type="button" onClick={() => setPage((current) => Math.max(0, current - 1))} disabled={page === 0}>Назад</button>
                <span>Страница {page + 1} из {Math.ceil(data.logs_total / pageSize)}</span>
                <button type="button" onClick={() => setPage((current) => current + 1)} disabled={(page + 1) * pageSize >= data.logs_total}>Дальше</button>
              </div>
            )}
          </section>
        </div>
      )}
    </ConsoleShell>
  );
}
