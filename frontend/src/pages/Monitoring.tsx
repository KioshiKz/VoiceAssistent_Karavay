import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { ordersApi } from "../api/endpoints";
import type { OrderLineHistoryEntryOut } from "../api/types";
import { ConsoleShell } from "../components/ConsoleShell";

const EVENT_LABELS: Record<string, string> = {
  create: "создание",
  edit: "редактирование",
  match: "сопоставление",
  cancel: "отмена",
  delete: "удаление",
};

export function Monitoring() {
  const [items, setItems] = useState<OrderLineHistoryEntryOut[]>([]);
  const [loading, setLoading] = useState(false);

  function reload() {
    setLoading(true);
    ordersApi
      .historyAll({ limit: 200 })
      .then(setItems)
      .finally(() => setLoading(false));
  }

  useEffect(reload, []);

  return (
    <ConsoleShell
      title="Мониторинг действий"
      subtitle="Кто и когда редактировал заявки — по всем заявкам, включая удалённые строки."
      actions={
        <button type="button" onClick={reload} disabled={loading}>
          <RefreshCw size={17} />
          Обновить
        </button>
      }
    >
      {items.length === 0 ? (
        <div className="empty-state">Изменений пока нет.</div>
      ) : (
        <div className="history-list">
          {items.map((item) => (
            <article key={item.id}>
              <strong>{EVENT_LABELS[item.event_type] ?? item.event_type}</strong>{" "}
              {item.product_name_raw && <span>{item.product_name_raw}</span>}
              <span>
                {item.actor_name ?? "система"} · {new Date(item.created_at).toLocaleString("ru-RU")}
                {item.execution_date && ` · заявка от ${item.execution_date}`}
              </span>
              {item.note && <p>{item.note}</p>}
            </article>
          ))}
        </div>
      )}
    </ConsoleShell>
  );
}
