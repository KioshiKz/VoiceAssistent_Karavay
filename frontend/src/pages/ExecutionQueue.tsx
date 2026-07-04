import { useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { ordersApi } from "../api/endpoints";
import type { CurrentOrderOut, OrderLineOut } from "../api/types";
import { ConsoleShell } from "../components/ConsoleShell";
import { ExecutionPanel } from "../components/ExecutionPanel";

function statusLabel(status: OrderLineOut["status"]) {
  if (status === "pending") return "ожидает";
  if (status === "in_progress") return "в работе";
  if (status === "completed") return "готово";
  return "отменена";
}

export function ExecutionQueue() {
  const [order, setOrder] = useState<CurrentOrderOut | null>(null);
  const [selectedLineId, setSelectedLineId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [empty, setEmpty] = useState(false);

  function reload() {
    setLoading(true);
    ordersApi
      .current()
      .then((next) => {
        setOrder(next);
        setEmpty(false);
      })
      .catch(() => {
        setOrder(null);
        setEmpty(true);
      })
      .finally(() => setLoading(false));
  }

  useEffect(reload, []);

  const groups = useMemo(() => {
    const map = new Map<string, OrderLineOut[]>();
    for (const line of order?.lines ?? []) {
      const key = line.workshop_folder_name ?? "Без цеха";
      map.set(key, [...(map.get(key) ?? []), line]);
    }
    return [...map.entries()];
  }, [order]);

  useEffect(() => {
    if (!order?.lines.length) {
      setSelectedLineId(null);
      return;
    }
    if (selectedLineId && order.lines.some((line) => line.id === selectedLineId)) return;
    const firstExecutable = order.lines.find((line) => line.match_status === "matched" && line.status !== "cancelled");
    setSelectedLineId(firstExecutable?.id ?? null);
  }, [order, selectedLineId]);

  return (
    <ConsoleShell
      title="Выполнение заявки"
      subtitle="Очередь видна только в пределах цехов и количества позиций, разрешённых ролью."
      actions={
        <button type="button" onClick={reload} disabled={loading}>
          <RefreshCw size={17} />
          Обновить
        </button>
      }
    >
      {empty || !order ? (
        <div className="empty-state">Заявки пока нет - ожидайте</div>
      ) : (
        <div className="execution-workspace">
          <aside className="execution-queue-panel">
            <div className="pane-heading">
              <div>
                <p className="eyebrow">Очередь</p>
                <h2>{order.execution_date}</h2>
              </div>
            </div>

            {groups.map(([groupName, lines]) => (
              <section className="execution-group" key={groupName}>
                <h3>{groupName}</h3>
                {lines.map((line) => {
                  const disabled = line.match_status !== "matched" || line.status === "cancelled";
                  return (
                    <button
                      key={line.id}
                      type="button"
                      className={`execution-line-button${selectedLineId === line.id ? " active" : ""}`}
                      onClick={() => setSelectedLineId(line.id)}
                      disabled={disabled}
                    >
                      <span>
                        <strong>{line.product_name_raw}</strong>
                        <small>
                          {line.due_time.slice(0, 5)} · {line.quantity} шт · {statusLabel(line.status)}
                        </small>
                      </span>
                    </button>
                  );
                })}
              </section>
            ))}
          </aside>

          <section className="execution-center">
            <ExecutionPanel orderLineId={selectedLineId} />
          </section>
        </div>
      )}
    </ConsoleShell>
  );
}
