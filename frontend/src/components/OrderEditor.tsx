import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, Edit3, History, Pin, Play, Plus, RefreshCw, Trash2, X, XCircle } from "lucide-react";
import { ordersApi, productsApi } from "../api/endpoints";
import type {
  CurrentOrderOut,
  OrderDetailOut,
  OrderLineHistoryEntryOut,
  OrderLineOut,
  ProductOut,
} from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { HISTORY_LABELS } from "../utils/orderHistory";
import { ConsoleShell } from "./ConsoleShell";
import { CurrentOrderSelection } from "./CurrentOrderSelection";

type OrderData = CurrentOrderOut | OrderDetailOut;

function isOrderDetail(order: OrderData): order is OrderDetailOut {
  return "source_filename" in order;
}

function parseExecutionDate(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function formatExecutionDate(value: string) {
  return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "long", year: "numeric" }).format(
    parseExecutionDate(value),
  );
}

function statusLabel(status: OrderLineOut["status"]) {
  if (status === "pending") return "ожидает";
  if (status === "in_progress") return "в работе";
  if (status === "completed") return "готово";
  return "отменена";
}

function orderStatusLabel(status: OrderDetailOut["status"]) {
  if (status === "pending") return "ожидает";
  if (status === "in_progress") return "в работе";
  return "завершена";
}

function progressLabel(line: OrderLineOut) {
  if (line.status === "completed" && !line.execution_plan_status) return "Выполнено принудительно";
  if (!line.execution_plan_status) return "Не начато";
  if (line.total_steps === 0) return line.execution_plan_status === "completed" ? "Выполнено" : "Нет шагов";
  if (line.execution_plan_status === "completed") return `Шаг ${line.total_steps} из ${line.total_steps}`;
  const current = Math.min((line.current_step_index ?? 0) + 1, line.total_steps);
  return `Шаг ${current} из ${line.total_steps}`;
}

function MatchResolver({
  line,
  products,
  onMatched,
}: {
  line: OrderLineOut;
  products: ProductOut[];
  onMatched: () => void;
}) {
  return (
    <div className="inline-match">
      <select
        aria-label={`Сопоставить продукцию ${line.product_name_raw}`}
        onChange={async (event) => {
          if (!event.target.value) return;
          await ordersApi.match(line.id, event.target.value);
          onMatched();
        }}
        defaultValue=""
      >
        <option value="" disabled>
          Выбрать продукцию цеха
        </option>
        {products.map((product) => (
          <option key={product.id} value={product.id}>
            {product.name}
          </option>
        ))}
      </select>
    </div>
  );
}

interface OrderEditorProps {
  fetchOrder: () => Promise<OrderData>;
  editTabKey: string;
  title: string;
  subtitle: string;
  allowCurrentSelection?: boolean;
}

export function OrderEditor({ fetchOrder, editTabKey, title, subtitle, allowCurrentSelection = false }: OrderEditorProps) {
  const navigate = useNavigate();
  const { hasTabEdit, hasGlobal } = useAuth();
  const canEdit = hasTabEdit(editTabKey);
  const canExecute = hasGlobal("order.execute");
  const canCreateLine = hasGlobal("order.line.create");
  const canDeleteLine = hasGlobal("order.line.delete");
  const canViewHistory = hasGlobal("order.history.view");
  const canForceComplete = hasGlobal("order.force_complete");
  const canSelectCurrent = hasGlobal("orders.select_current");

  const [order, setOrder] = useState<OrderData | null>(null);
  const [currentContext, setCurrentContext] = useState<{
    workshop_folder_id: string;
    execution_date: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [availableProducts, setAvailableProducts] = useState<ProductOut[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [editLine, setEditLine] = useState<OrderLineOut | null>(null);
  const [editDraft, setEditDraft] = useState({ product_name_raw: "", quantity: 1, due_time: "00:00" });
  const [cancelLine, setCancelLine] = useState<OrderLineOut | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [deleteLine, setDeleteLine] = useState<OrderLineOut | null>(null);
  const [creating, setCreating] = useState(false);
  const [createDraft, setCreateDraft] = useState({ product_id: "", quantity: 1, due_time: "00:00" });
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyItems, setHistoryItems] = useState<OrderLineHistoryEntryOut[]>([]);
  const [forceCompleteOpen, setForceCompleteOpen] = useState(false);
  const [forceCompleting, setForceCompleting] = useState(false);
  const [selectingCurrent, setSelectingCurrent] = useState(false);
  const [currentSelectionNotice, setCurrentSelectionNotice] = useState<string | null>(null);
  const reloadGeneration = useRef(0);

  const reload = useCallback(() => {
    const generation = ++reloadGeneration.current;
    setError(null);
    setActionError(null);
    setCurrentSelectionNotice(null);
    const request = allowCurrentSelection && currentContext ? ordersApi.current(currentContext) : fetchOrder();
    return request
      .then((nextOrder) => {
        if (generation === reloadGeneration.current) setOrder(nextOrder);
      })
      .catch(() => {
        if (generation !== reloadGeneration.current) return;
        setOrder(null);
        setError("Заявка не найдена или недоступна.");
      });
  }, [allowCurrentSelection, currentContext, fetchOrder]);

  useEffect(() => {
    void reload();
    return () => {
      reloadGeneration.current += 1;
    };
  }, [reload]);

  const workshopId = order
    ? isOrderDetail(order)
      ? order.workshop_folder_id
      : (order.workshop_folder_id ?? order.lines.find((line) => line.workshop_folder_id)?.workshop_folder_id ?? null)
    : null;

  useEffect(() => {
    if (!workshopId) {
      setAvailableProducts([]);
      return;
    }
    let active = true;
    setProductsLoading(true);
    productsApi
      .availableForWorkshop(workshopId)
      .then((products) => {
        if (!active) return;
        setAvailableProducts([...products].sort((a, b) => a.name.localeCompare(b.name, "ru")));
      })
      .catch(() => {
        if (active) setAvailableProducts([]);
      })
      .finally(() => {
        if (active) setProductsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [workshopId]);

  const detail = order && isOrderDetail(order) ? order : null;
  const canAddProduct = canCreateLine && !!workshopId && detail?.status !== "completed";
  const sortedHistory = useMemo(
    () => [...historyItems].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [historyItems],
  );

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
    setActionError(null);
    try {
      await ordersApi.updateLine(editLine.id, {
        product_name_raw: editDraft.product_name_raw,
        quantity: editDraft.quantity,
        due_time: editDraft.due_time,
      });
      setEditLine(null);
      await reload();
    } catch {
      setActionError("Не удалось сохранить изменения.");
    }
  }

  async function saveCancel() {
    if (!cancelLine || !cancelReason.trim()) return;
    setActionError(null);
    try {
      await ordersApi.cancelLine(cancelLine.id, cancelReason.trim());
      setCancelLine(null);
      setCancelReason("");
      await reload();
    } catch {
      setActionError("Не удалось отменить продукцию.");
    }
  }

  async function confirmDelete() {
    if (!deleteLine) return;
    setActionError(null);
    try {
      await ordersApi.deleteLine(deleteLine.id);
      setDeleteLine(null);
      await reload();
    } catch {
      setActionError("Не удалось удалить продукцию из заявки.");
    }
  }

  function openCreate() {
    setCreateDraft({ product_id: availableProducts[0]?.id ?? "", quantity: 1, due_time: "00:00" });
    setCreating(true);
  }

  async function saveCreate() {
    if (!order || !createDraft.product_id) return;
    const product = availableProducts.find((item) => item.id === createDraft.product_id);
    if (!product) return;
    setActionError(null);
    try {
      await ordersApi.createLine({
        order_id: order.order_id,
        product_name_raw: product.name,
        quantity: createDraft.quantity,
        due_time: createDraft.due_time,
        matched_product_id: product.id,
      });
      setCreating(false);
      await reload();
    } catch {
      setActionError("Не удалось добавить продукцию.");
    }
  }

  async function openHistory() {
    if (!order || !canViewHistory) return;
    setHistoryOpen(true);
    setHistoryLoading(true);
    try {
      setHistoryItems(await ordersApi.historyAll({ order_id: order.order_id, limit: 500 }));
    } catch {
      setHistoryItems([]);
      setActionError("Не удалось загрузить историю заявки.");
    } finally {
      setHistoryLoading(false);
    }
  }

  async function confirmForceComplete() {
    if (!detail) return;
    setForceCompleting(true);
    setActionError(null);
    try {
      await ordersApi.forceComplete(detail.order_id);
      setForceCompleteOpen(false);
      if (detail.workshop_folder_id) {
        navigate(`/workshops/${detail.workshop_folder_id}/orders`);
      } else {
        await reload();
      }
    } catch {
      setActionError("Не удалось завершить заявку принудительно.");
    } finally {
      setForceCompleting(false);
    }
  }

  async function makeCurrent() {
    if (!detail?.workshop_folder_id || detail.status === "completed") return;
    setSelectingCurrent(true);
    setActionError(null);
    setCurrentSelectionNotice(null);
    try {
      await ordersApi.setCurrentSelection(detail.workshop_folder_id, detail.execution_date, detail.order_id);
      setCurrentSelectionNotice("Заявка выбрана текущей для этого цеха и даты.");
    } catch {
      setActionError("Не удалось сделать заявку текущей.");
    } finally {
      setSelectingCurrent(false);
    }
  }

  function showSelectedCurrentOrder(nextOrder: CurrentOrderOut) {
    reloadGeneration.current += 1;
    setError(null);
    setActionError(null);
    setCurrentSelectionNotice(null);
    setOrder(nextOrder);
    setCurrentContext(
      nextOrder.workshop_folder_id
        ? { workshop_folder_id: nextOrder.workshop_folder_id, execution_date: nextOrder.execution_date }
        : null,
    );
  }

  return (
    <ConsoleShell
      title={title}
      subtitle={subtitle}
      actions={
        <div className="order-toolbar">
          {canAddProduct && order && (
            <button type="button" onClick={openCreate} disabled={productsLoading}>
              <Plus size={17} />
              Добавить продукцию
            </button>
          )}
          {canViewHistory && order && (
            <button type="button" onClick={() => void openHistory()}>
              <History size={17} />
              История заявки
            </button>
          )}
          {canForceComplete && detail && detail.status !== "completed" && (
            <button type="button" className="danger" onClick={() => setForceCompleteOpen(true)}>
              <CheckCircle2 size={17} />
              Завершить принудительно
            </button>
          )}
          {canSelectCurrent && detail?.workshop_folder_id && detail.status !== "completed" && (
            <button type="button" onClick={() => void makeCurrent()} disabled={selectingCurrent}>
              <Pin size={17} />
              {selectingCurrent ? "Выбор..." : "Сделать текущей"}
            </button>
          )}
          <button type="button" onClick={() => void reload()}>
            <RefreshCw size={17} />
            Обновить
          </button>
        </div>
      }
    >
      {error && <div className="empty-state">{error}</div>}
      {actionError && <p className="error-text order-action-error">{actionError}</p>}
      {currentSelectionNotice && <p className="current-order-selection-notice">{currentSelectionNotice}</p>}

      {allowCurrentSelection && (
        <CurrentOrderSelection
          currentOrder={order && !isOrderDetail(order) ? order : null}
          onChanged={showSelectedCurrentOrder}
        />
      )}

      {order && (
        <>
          <section className="order-detail-summary">
            <article>
              <small>Дата исполнения</small>
              <strong>{formatExecutionDate(order.execution_date)}</strong>
            </article>
            {detail && (
              <>
                <article>
                  <small>Цех</small>
                  <strong>{detail.workshop_folder_name ?? "—"}</strong>
                </article>
                <article>
                  <small>Исходный файл</small>
                  <strong>{detail.source_filename ?? "Создана вручную"}</strong>
                </article>
                <article>
                  <small>Загрузил</small>
                  <strong>{detail.uploaded_by_name ?? "Система"}</strong>
                  <span>{new Date(detail.uploaded_at).toLocaleString("ru-RU")}</span>
                </article>
                <article>
                  <small>Статус</small>
                  <strong>{orderStatusLabel(detail.status)}</strong>
                  {detail.force_completed_at && (
                    <span>
                      Принудительно завершил {detail.force_completed_by_name ?? "пользователь"},{" "}
                      {new Date(detail.force_completed_at).toLocaleString("ru-RU")}
                    </span>
                  )}
                </article>
              </>
            )}
          </section>

          <section className="editor-card order-detail-card">
            <div className="pane-heading">
              <div>
                <p className="eyebrow">Состав заявки</p>
                <h2>{order.lines.length} позиций</h2>
              </div>
            </div>

            {order.lines.length === 0 ? (
              <div className="empty-state">В заявке пока нет продукции.</div>
            ) : (
              <div className="order-table-scroll">
                <table className="order-table">
                  <thead>
                    <tr>
                      <th>Продукция</th>
                      <th>Количество</th>
                      <th>Время</th>
                      <th>Статус</th>
                      <th>Шаг выполнения</th>
                      <th>Исполнитель</th>
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {order.lines.map((line) => (
                      <tr key={line.id} className={line.status === "cancelled" ? "muted-row" : ""}>
                        <td>
                          <strong>{line.product_name_raw}</strong>
                          {line.match_status === "unmatched" && !canEdit && (
                            <small className="table-note">не сопоставлена</small>
                          )}
                        </td>
                        <td>{line.quantity}</td>
                        <td>{line.due_time.slice(0, 5)}</td>
                        <td>
                          <span className={`badge status-${line.status}`}>{statusLabel(line.status)}</span>
                          {line.cancellation_reason && <small className="table-note">{line.cancellation_reason}</small>}
                        </td>
                        <td>
                          {line.match_status === "matched" ? (
                            <div className="execution-progress-cell">
                              <strong>{progressLabel(line)}</strong>
                              {line.current_step_name && <small>{line.current_step_name}</small>}
                              {canExecute && line.status !== "cancelled" && line.status !== "completed" && (
                                <button type="button" onClick={() => navigate(`/orders/current/${line.id}/execute`)}>
                                  <Play size={15} />
                                  Открыть
                                </button>
                              )}
                            </div>
                          ) : canEdit && line.status !== "cancelled" && line.status !== "completed" ? (
                            <MatchResolver line={line} products={availableProducts} onMatched={() => void reload()} />
                          ) : (
                            <span className="badge unmatched">не найдено</span>
                          )}
                        </td>
                        <td>
                          {line.last_advanced_by_name ? (
                            <span className="executor-cell">
                              <strong>{line.last_advanced_by_name}</strong>
                              {line.last_advanced_at && (
                                <small>{new Date(line.last_advanced_at).toLocaleString("ru-RU")}</small>
                              )}
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td>
                          <div className="table-actions">
                            {canEdit &&
                              line.status !== "cancelled" &&
                              line.status !== "completed" &&
                              !line.execution_plan_status && (
                                <button type="button" onClick={() => openEdit(line)} title="Редактировать">
                                  <Edit3 size={15} />
                                </button>
                              )}
                            {canEdit && line.status !== "cancelled" && line.status !== "completed" && (
                                <button
                                  type="button"
                                  className="danger"
                                  onClick={() => setCancelLine(line)}
                                  title="Отменить"
                                >
                                  <XCircle size={15} />
                                </button>
                            )}
                            {canDeleteLine && detail?.status !== "completed" && (
                              <button
                                type="button"
                                className="danger"
                                onClick={() => setDeleteLine(line)}
                                title="Удалить"
                              >
                                <Trash2 size={15} />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}

      {creating && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setCreating(false)}>
          <div className="modal-card" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Добавить продукцию</h2>
                <p>Доступен только ассортимент выбранного цеха.</p>
              </div>
              <button type="button" className="icon-button" onClick={() => setCreating(false)} title="Закрыть">
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <label className="modal-field">
                Продукция
                <select
                  value={createDraft.product_id}
                  onChange={(event) => setCreateDraft((prev) => ({ ...prev, product_id: event.target.value }))}
                  autoFocus
                >
                  {availableProducts.length === 0 && <option value="">Нет доступной продукции</option>}
                  {availableProducts.map((product) => (
                    <option key={product.id} value={product.id}>
                      {product.name}
                    </option>
                  ))}
                </select>
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
              <button
                className="primary"
                type="button"
                onClick={() => void saveCreate()}
                disabled={!createDraft.product_id || createDraft.quantity < 1}
              >
                Добавить
              </button>
            </div>
          </div>
        </div>
      )}

      {editLine && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setEditLine(null)}>
          <div className="modal-card" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Редактировать продукцию</h2>
                <p>{editLine.product_name_raw}</p>
              </div>
              <button type="button" className="icon-button" onClick={() => setEditLine(null)} title="Закрыть">
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <label className="modal-field">
                Название
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
              <button className="primary" type="button" onClick={() => void saveEdit()}>
                Сохранить
              </button>
            </div>
          </div>
        </div>
      )}

      {cancelLine && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setCancelLine(null)}>
          <div className="modal-card" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Отменить продукцию</h2>
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
              <button className="danger" type="button" onClick={() => void saveCancel()} disabled={!cancelReason.trim()}>
                Отменить
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteLine && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setDeleteLine(null)}>
          <div className="modal-card" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Удалить продукцию из заявки</h2>
                <p>{deleteLine.product_name_raw}</p>
              </div>
              <button type="button" className="icon-button" onClick={() => setDeleteLine(null)} title="Закрыть">
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <p className="dialog-message">Строка будет удалена, но запись об этом останется в истории заявки.</p>
            </div>
            <div className="modal-footer">
              <button type="button" onClick={() => setDeleteLine(null)}>
                Назад
              </button>
              <button className="danger" type="button" onClick={() => void confirmDelete()}>
                Удалить
              </button>
            </div>
          </div>
        </div>
      )}

      {historyOpen && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setHistoryOpen(false)}>
          <div
            className="modal-card order-history-modal"
            role="dialog"
            aria-modal="true"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h2>История заявки</h2>
                <p>{order ? formatExecutionDate(order.execution_date) : ""}</p>
              </div>
              <button type="button" className="icon-button" onClick={() => setHistoryOpen(false)} title="Закрыть">
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              {historyLoading ? (
                <div className="empty-folder">Загрузка истории...</div>
              ) : sortedHistory.length === 0 ? (
                <div className="empty-folder">Истории пока нет.</div>
              ) : (
                <div className="history-list">
                  {sortedHistory.map((item) => (
                    <article key={item.id}>
                      <strong>{HISTORY_LABELS[item.event_type] ?? item.event_type}</strong>
                      {item.product_name_raw && <span>{item.product_name_raw}</span>}
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

      {forceCompleteOpen && detail && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => !forceCompleting && setForceCompleteOpen(false)}>
          <div className="modal-card" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Завершить заявку принудительно</h2>
                <p>{formatExecutionDate(detail.execution_date)}</p>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={() => setForceCompleteOpen(false)}
                disabled={forceCompleting}
                title="Закрыть"
              >
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <p className="dialog-message">
                Все незавершённые позиции будут отмечены выполненными. Действие сохранится в истории заявки.
              </p>
            </div>
            <div className="modal-footer">
              <button type="button" onClick={() => setForceCompleteOpen(false)} disabled={forceCompleting}>
                Назад
              </button>
              <button className="danger" type="button" onClick={() => void confirmForceComplete()} disabled={forceCompleting}>
                {forceCompleting ? "Завершение..." : "Завершить"}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConsoleShell>
  );
}
