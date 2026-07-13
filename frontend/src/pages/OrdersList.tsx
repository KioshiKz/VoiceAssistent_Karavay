import { useEffect, useMemo, useState } from "react";
import { FileUp, History, Plus, X } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { foldersApi, ordersApi } from "../api/endpoints";
import type { FolderOut, OrderStatus, OrderSummaryOut } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ConsoleShell } from "../components/ConsoleShell";
import { OrderUploadDialog } from "../components/OrderUploadDialog";

type ListMode = "active" | "history";

function localDateValue(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseExecutionDate(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function formatExecutionDate(value: string) {
  return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" }).format(
    parseExecutionDate(value),
  );
}

function formatMonth(value: string) {
  const date = parseExecutionDate(value);
  const month = new Intl.DateTimeFormat("ru-RU", { month: "long" }).format(date);
  const capitalizedMonth = month.charAt(0).toLocaleUpperCase("ru-RU") + month.slice(1);
  return `${capitalizedMonth} ${date.getFullYear()}`;
}

function formatUploadTime(value: string) {
  return new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function statusLabel(status: OrderStatus) {
  if (status === "completed") return "завершена";
  if (status === "in_progress") return "в работе";
  return "ожидает";
}

export function OrdersList() {
  const navigate = useNavigate();
  const { workshopId = "" } = useParams<{ workshopId: string }>();
  const { hasGlobal, hasTabEdit } = useAuth();
  const canEditOrders = hasTabEdit("orders_list");
  const canViewHistory = hasGlobal("order.history.view");

  const [orders, setOrders] = useState<OrderSummaryOut[]>([]);
  const [workshop, setWorkshop] = useState<FolderOut | null>(null);
  const [mode, setMode] = useState<ListMode>("active");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createDate, setCreateDate] = useState(localDateValue);
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    Promise.all([ordersApi.list(workshopId, mode === "history"), foldersApi.tree()])
      .then(([nextOrders, folders]) => {
        if (!active) return;
        setOrders(nextOrders);
        setWorkshop(folders.find((folder) => folder.id === workshopId && folder.parent_id === null) ?? null);
      })
      .catch(() => {
        if (active) setError("Не удалось загрузить заявки этого цеха.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [mode, workshopId]);

  const groupedOrders = useMemo(() => {
    const visible = orders
      .filter((order) => (mode === "history" ? order.status === "completed" : order.status !== "completed"))
      .sort((a, b) =>
        b.execution_date.localeCompare(a.execution_date) || b.uploaded_at.localeCompare(a.uploaded_at),
      );
    const groups = new Map<string, OrderSummaryOut[]>();
    for (const order of visible) {
      const key = order.execution_date.slice(0, 7);
      groups.set(key, [...(groups.get(key) ?? []), order]);
    }
    return [...groups.entries()].map(([key, items]) => ({ key, label: formatMonth(items[0].execution_date), items }));
  }, [mode, orders]);

  async function createOrder() {
    if (!workshopId || !createDate) return;
    setCreating(true);
    setCreateError(null);
    try {
      const created = await ordersApi.create({ execution_date: createDate, workshop_folder_id: workshopId });
      setCreateOpen(false);
      navigate(`/workshops/${workshopId}/orders/${created.order_id}`);
    } catch {
      setCreateError("Не удалось создать заявку.");
    } finally {
      setCreating(false);
    }
  }

  const workshopName = workshop?.name ?? "Выбранный цех";

  return (
    <ConsoleShell
      title={`Заявки: ${workshopName}`}
      subtitle={
        mode === "history"
          ? "Завершённые заявки цеха, сгруппированные по месяцам."
          : "Активные заявки цеха, сгруппированные по месяцам."
      }
      actions={
        <div className="order-toolbar">
          {canEditOrders && (
            <button type="button" onClick={() => setUploadOpen(true)}>
              <FileUp size={17} />
              Загрузить
            </button>
          )}
          {canEditOrders && (
            <button type="button" onClick={() => setCreateOpen(true)}>
              <Plus size={17} />
              Создать заявку
            </button>
          )}
          {canViewHistory && (
            <button
              type="button"
              className={mode === "history" ? "active" : ""}
              aria-pressed={mode === "history"}
              onClick={() => setMode((current) => (current === "history" ? "active" : "history"))}
            >
              <History size={17} />
              История заявок
            </button>
          )}
        </div>
      }
    >
      {loading ? (
        <div className="empty-state">Загрузка заявок...</div>
      ) : error ? (
        <div className="empty-state">{error}</div>
      ) : groupedOrders.length === 0 ? (
        <div className="empty-state">
          {mode === "history" ? "Завершённых заявок пока нет." : "Активных заявок пока нет."}
        </div>
      ) : (
        <div className="orders-by-month">
          {groupedOrders.map((group) => (
            <section className="orders-month" key={group.key}>
              <h2>{group.label}</h2>
              <div className="orders-month-list">
                {group.items.map((order) => (
                  <Link
                    className="order-list-row"
                    key={order.id}
                    to={`/workshops/${workshopId}/orders/${order.id}`}
                  >
                    <span className="order-list-main">
                      <strong>
                        Заявка {formatExecutionDate(order.execution_date)} — {order.source_filename ? "загружена" : "создана"}{" "}
                        {formatUploadTime(order.uploaded_at)}
                      </strong>
                      <small>
                        {order.total_lines} позиций · {statusLabel(order.status)}
                      </small>
                    </span>
                    <span className="order-list-author">
                      <small>{order.source_filename ? "Загрузил" : "Создал"}</small>
                      <strong>{order.uploaded_by_name ?? "Система"}</strong>
                    </span>
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {uploadOpen && (
        <OrderUploadDialog
          workshopId={workshopId}
          workshopName={workshopName}
          onClose={() => setUploadOpen(false)}
          onUploaded={(orderId) => navigate(`/workshops/${workshopId}/orders/${orderId}`)}
        />
      )}

      {createOpen && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => !creating && setCreateOpen(false)}>
          <div className="modal-card" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Создать заявку</h2>
                <p>Цех: {workshopName}</p>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={() => setCreateOpen(false)}
                disabled={creating}
                title="Закрыть"
              >
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <label className="modal-field">
                Дата исполнения
                <input
                  type="date"
                  value={createDate}
                  onChange={(event) => setCreateDate(event.target.value)}
                  disabled={creating}
                />
              </label>
              <p className="dialog-message">После создания откроется заявка, в которую можно добавить продукцию.</p>
              {createError && <p className="error-text">{createError}</p>}
            </div>
            <div className="modal-footer">
              <button type="button" onClick={() => setCreateOpen(false)} disabled={creating}>
                Отмена
              </button>
              <button className="primary" type="button" onClick={() => void createOrder()} disabled={creating || !createDate}>
                {creating ? "Создание..." : "Создать"}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConsoleShell>
  );
}
