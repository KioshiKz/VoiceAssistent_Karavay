import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Edit3, History, Play, Plus, RefreshCw, Search, Trash2, X, XCircle } from "lucide-react";
import { ordersApi, productsApi } from "../api/endpoints";
import type { CurrentOrderOut, OrderLineHistoryOut, OrderLineOut, ProductOut } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ConsoleShell } from "./ConsoleShell";

function statusLabel(status: OrderLineOut["status"]) {
  if (status === "pending") return "ожидает";
  if (status === "in_progress") return "в работе";
  if (status === "completed") return "готово";
  return "отменена";
}

function MatchResolver({ line, onMatched }: { line: OrderLineOut; onMatched: () => void }) {
  const [query, setQuery] = useState(line.product_name_raw);
  const [results, setResults] = useState<ProductOut[]>([]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      productsApi.search(query).then(setResults);
    }, 250);
    return () => window.clearTimeout(handle);
  }, [query]);

  return (
    <div className="inline-match">
      <Search size={15} />
      <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Найти продукцию..." />
      <select
        onChange={async (event) => {
          if (!event.target.value) return;
          await ordersApi.match(line.id, event.target.value);
          onMatched();
        }}
        defaultValue=""
      >
        <option value="" disabled>
          Выбрать
        </option>
        {results.map((product) => (
          <option key={product.id} value={product.id}>
            {product.name}
          </option>
        ))}
      </select>
    </div>
  );
}

interface OrderEditorProps {
  fetchOrder: () => Promise<CurrentOrderOut>;
  editTabKey: string;
  title: string;
  subtitle: string;
}

export function OrderEditor({ fetchOrder, editTabKey, title, subtitle }: OrderEditorProps) {
  const navigate = useNavigate();
  const { hasTabEdit, hasGlobal } = useAuth();
  const canEdit = hasTabEdit(editTabKey);
  const canExecute = hasGlobal("order.execute");
  const [order, setOrder] = useState<CurrentOrderOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editLine, setEditLine] = useState<OrderLineOut | null>(null);
  const [editDraft, setEditDraft] = useState({ product_name_raw: "", quantity: 1, due_time: "00:00" });
  const [cancelLine, setCancelLine] = useState<OrderLineOut | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [historyLine, setHistoryLine] = useState<OrderLineOut | null>(null);
  const [historyItems, setHistoryItems] = useState<OrderLineHistoryOut[]>([]);
  const [deleteLine, setDeleteLine] = useState<OrderLineOut | null>(null);
  const [creating, setCreating] = useState(false);
  const [createDraft, setCreateDraft] = useState({ product_name_raw: "", quantity: 1, due_time: "00:00" });

  function reload() {
    setError(null);
    fetchOrder()
      .then(setOrder)
      .catch(() => {
        setOrder(null);
        setError("Заявки пока нет - ожидайте");
      });
  }

  useEffect(reload, [fetchOrder]);

  function openEdit(line: OrderLineOut) {
    setEditLine(line);
    setEditDraft({
      product_name_raw: line.product_name_raw,
      quantity: line.quantity,
      due_time: line.due_time.slice(0, 5),
    });
  }

  async function saveEdit() {
    if (!editLine) return;
    await ordersApi.updateLine(editLine.id, {
      product_name_raw: editDraft.product_name_raw,
      quantity: editDraft.quantity,
      due_time: editDraft.due_time,
    });
    setEditLine(null);
    reload();
  }

  async function saveCancel() {
    if (!cancelLine || !cancelReason.trim()) return;
    await ordersApi.cancelLine(cancelLine.id, cancelReason.trim());
    setCancelLine(null);
    setCancelReason("");
    reload();
  }

  async function confirmDelete() {
    if (!deleteLine) return;
    await ordersApi.deleteLine(deleteLine.id);
    setDeleteLine(null);
    reload();
  }

  async function openHistory(line: OrderLineOut) {
    setHistoryLine(line);
    setHistoryItems(await ordersApi.history(line.id));
  }

  async function saveCreate() {
    if (!order || !createDraft.product_name_raw.trim()) return;
    await ordersApi.createLine({
      order_id: order.order_id,
      product_name_raw: createDraft.product_name_raw.trim(),
      quantity: createDraft.quantity,
      due_time: createDraft.due_time,
    });
    setCreating(false);
    setCreateDraft({ product_name_raw: "", quantity: 1, due_time: "00:00" });
    reload();
  }

  return (
    <ConsoleShell
      title={title}
      subtitle={subtitle}
      actions={
        <div style={{ display: "flex", gap: 8 }}>
          {canEdit && order && (
            <button type="button" onClick={() => setCreating(true)}>
              <Plus size={17} />
              Добавить строку
            </button>
          )}
          <button type="button" onClick={reload}>
            <RefreshCw size={17} />
            Обновить
          </button>
        </div>
      }
    >
      {error && <div className="empty-state">{error}</div>}

      {order && (
        <section className="editor-card">
          <div className="pane-heading">
            <div>
              <p className="eyebrow">Дата исполнения</p>
              <h2>{order.execution_date}</h2>
            </div>
          </div>

          <table className="order-table">
            <thead>
              <tr>
                <th>Цех</th>
                <th>Продукция</th>
                <th>Количество</th>
                <th>Время</th>
                <th>Статус</th>
                <th>Исполнение</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {order.lines.map((line) => (
                <tr key={line.id} className={line.status === "cancelled" ? "muted-row" : ""}>
                  <td>{line.workshop_folder_name ?? "Без цеха"}</td>
                  <td>{line.product_name_raw}</td>
                  <td>{line.quantity}</td>
                  <td>{line.due_time.slice(0, 5)}</td>
                  <td>
                    <span className={`badge status-${line.status}`}>{statusLabel(line.status)}</span>
                    {line.cancellation_reason && <small className="table-note">{line.cancellation_reason}</small>}
                  </td>
                  <td>
                    {line.match_status === "matched" ? (
                      <button
                        type="button"
                        onClick={() => navigate(`/orders/current/${line.id}/execute`)}
                        disabled={!canExecute || line.status === "cancelled"}
                      >
                        <Play size={15} />
                        Открыть
                      </button>
                    ) : canEdit ? (
                      <MatchResolver line={line} onMatched={reload} />
                    ) : (
                      <span className="badge unmatched">не найдено</span>
                    )}
                    {line.last_advanced_by_name && (
                      <small className="table-note">
                        продолжил {line.last_advanced_by_name}, {line.last_advanced_at?.slice(11, 16)}
                      </small>
                    )}
                  </td>
                  <td>
                    <div className="table-actions">
                      <button type="button" onClick={() => openHistory(line)} title="История">
                        <History size={15} />
                      </button>
                      {canEdit && line.status !== "cancelled" && (
                        <>
                          <button type="button" onClick={() => openEdit(line)} title="Редактировать">
                            <Edit3 size={15} />
                          </button>
                          <button type="button" className="danger" onClick={() => setCancelLine(line)} title="Отменить">
                            <XCircle size={15} />
                          </button>
                        </>
                      )}
                      {canEdit && (
                        <button type="button" className="danger" onClick={() => setDeleteLine(line)} title="Удалить">
                          <Trash2 size={15} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {creating && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setCreating(false)}>
          <div className="modal-card" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Новая строка заявки</h2>
              </div>
              <button type="button" className="icon-button" onClick={() => setCreating(false)} title="Закрыть">
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <label className="modal-field">
                Продукция
                <input
                  value={createDraft.product_name_raw}
                  onChange={(event) => setCreateDraft((prev) => ({ ...prev, product_name_raw: event.target.value }))}
                  autoFocus
                />
              </label>
              <label className="modal-field">
                Количество
                <input
                  type="number"
                  min={1}
                  value={createDraft.quantity}
                  onChange={(event) => setCreateDraft((prev) => ({ ...prev, quantity: Number(event.target.value) }))}
                />
              </label>
              <label className="modal-field">
                Время
                <input
                  type="time"
                  value={createDraft.due_time}
                  onChange={(event) => setCreateDraft((prev) => ({ ...prev, due_time: event.target.value }))}
                />
              </label>
            </div>
            <div className="modal-footer">
              <button type="button" onClick={() => setCreating(false)}>
                Отмена
              </button>
              <button className="primary" type="button" onClick={saveCreate} disabled={!createDraft.product_name_raw.trim()}>
                Добавить
              </button>
            </div>
          </div>
        </div>
      )}

      {editLine && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setEditLine(null)}>
          <div className="modal-card" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Редактировать заявку</h2>
                <p>{editLine.product_name_raw}</p>
              </div>
              <button type="button" className="icon-button" onClick={() => setEditLine(null)} title="Закрыть">
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <label className="modal-field">
                Продукция
                <input
                  value={editDraft.product_name_raw}
                  onChange={(event) => setEditDraft((prev) => ({ ...prev, product_name_raw: event.target.value }))}
                />
              </label>
              <label className="modal-field">
                Количество
                <input
                  type="number"
                  min={1}
                  value={editDraft.quantity}
                  onChange={(event) => setEditDraft((prev) => ({ ...prev, quantity: Number(event.target.value) }))}
                />
              </label>
              <label className="modal-field">
                Время
                <input
                  type="time"
                  value={editDraft.due_time}
                  onChange={(event) => setEditDraft((prev) => ({ ...prev, due_time: event.target.value }))}
                />
              </label>
            </div>
            <div className="modal-footer">
              <button type="button" onClick={() => setEditLine(null)}>
                Отмена
              </button>
              <button className="primary" type="button" onClick={saveEdit}>
                Сохранить
              </button>
            </div>
          </div>
        </div>
      )}

      {cancelLine && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setCancelLine(null)}>
          <div className="modal-card" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Отменить заявку</h2>
                <p>{cancelLine.product_name_raw}</p>
              </div>
              <button type="button" className="icon-button" onClick={() => setCancelLine(null)} title="Закрыть">
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <label className="modal-field">
                Причина отмены
                <textarea value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} autoFocus />
              </label>
            </div>
            <div className="modal-footer">
              <button type="button" onClick={() => setCancelLine(null)}>
                Назад
              </button>
              <button className="danger" type="button" onClick={saveCancel} disabled={!cancelReason.trim()}>
                Отменить заявку
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteLine && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setDeleteLine(null)}>
          <div className="modal-card" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Удалить строку заявки</h2>
                <p>{deleteLine.product_name_raw}</p>
              </div>
              <button type="button" className="icon-button" onClick={() => setDeleteLine(null)} title="Закрыть">
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <p>Строка будет удалена без возможности восстановления. История изменений останется в мониторинге.</p>
            </div>
            <div className="modal-footer">
              <button type="button" onClick={() => setDeleteLine(null)}>
                Назад
              </button>
              <button className="danger" type="button" onClick={confirmDelete}>
                Удалить
              </button>
            </div>
          </div>
        </div>
      )}

      {historyLine && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setHistoryLine(null)}>
          <div className="modal-card" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>История заявки</h2>
                <p>{historyLine.product_name_raw}</p>
              </div>
              <button type="button" className="icon-button" onClick={() => setHistoryLine(null)} title="Закрыть">
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              {historyItems.length === 0 ? (
                <div className="empty-folder">Истории пока нет.</div>
              ) : (
                <div className="history-list">
                  {historyItems.map((item) => (
                    <article key={item.id}>
                      <strong>{item.event_type}</strong>
                      <span>
                        {item.actor_name ?? "система"} · {new Date(item.created_at).toLocaleString("ru-RU")}
                      </span>
                      {item.note && <p>{item.note}</p>}
                    </article>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </ConsoleShell>
  );
}
