import { useCallback, useEffect, useMemo, useState } from "react";
import { isAxiosError } from "axios";
import { AlertTriangle, ArrowLeft, Plus, RefreshCw, RotateCcw, Save, Trash2 } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { emergencyApi, ordersApi, productsApi } from "../api/endpoints";
import type { EmergencyScheduleOut, OrderDetailOut, ProductOut } from "../api/types";
import { ConsoleShell } from "../components/ConsoleShell";
import { formatYield, isValidYieldQuantity, YIELD_UNIT_LABELS, yieldStep } from "../utils/units";

function errorText(error: unknown) {
  const detail = isAxiosError(error) ? error.response?.data?.detail : null;
  const labels: Record<string, string> = {
    emergency_source_line_already_started: "Эта позиция уже выполняется. Её нельзя заменить без потери текущего шага.",
    emergency_item_already_started: "Экстренная позиция уже выполняется и защищена от изменения.",
    order_already_completed: "Заявка уже завершена.",
  };
  return typeof detail === "string" ? labels[detail] ?? detail : "Операция не выполнена.";
}

export function EmergencySchedule() {
  const { orderId = "" } = useParams<{ orderId: string }>();
  const [order, setOrder] = useState<OrderDetailOut | null>(null);
  const [schedule, setSchedule] = useState<EmergencyScheduleOut | null>(null);
  const [products, setProducts] = useState<ProductOut[]>([]);
  const [reason, setReason] = useState("");
  const [draftQuantities, setDraftQuantities] = useState<Record<string, number>>({});
  const [addDraft, setAddDraft] = useState({ product_id: "", quantity: 1, due_time: "00:00" });
  const addUnit = products.find((product) => product.id === addDraft.product_id)?.yield_unit;
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!orderId) return;
    setLoading(true);
    setError(null);
    try {
      const nextOrder = await ordersApi.getOrder(orderId);
      setOrder(nextOrder);
      if (nextOrder.workshop_folder_id) {
        const nextProducts = await productsApi.availableForWorkshop(nextOrder.workshop_folder_id);
        setProducts(nextProducts);
        setAddDraft((current) => ({ ...current, product_id: current.product_id || nextProducts[0]?.id || "" }));
      }
      try {
        setSchedule(await emergencyApi.get(orderId));
      } catch (scheduleError) {
        if (isAxiosError(scheduleError) && scheduleError.response?.status === 404) setSchedule(null);
        else throw scheduleError;
      }
    } catch (loadError) {
      setError(errorText(loadError));
    } finally {
      setLoading(false);
    }
  }, [orderId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!schedule) return;
    const quantities: Record<string, number> = {};
    for (const line of schedule.source_lines) {
      const overlay = schedule.items.find((item) => item.id === line.overlaid_by_item_id);
      quantities[line.id] = overlay?.action === "replace" ? overlay.quantity : line.quantity;
    }
    for (const item of schedule.items) quantities[item.id] = item.quantity;
    setDraftQuantities(quantities);
  }, [schedule]);

  const overlayBySource = useMemo(
    () => new Map(schedule?.items.filter((item) => item.source_line_id).map((item) => [item.source_line_id!, item]) ?? []),
    [schedule],
  );

  async function run(action: () => Promise<EmergencyScheduleOut>) {
    setSaving(true);
    setError(null);
    try {
      setSchedule(await action());
    } catch (actionError) {
      setError(errorText(actionError));
    } finally {
      setSaving(false);
    }
  }

  async function activate() {
    if (!reason.trim()) return;
    await run(() => emergencyApi.create(orderId, reason.trim()));
  }

  async function replaceSource(sourceLineId: string) {
    if (!schedule) return;
    await run(() =>
      emergencyApi.replace(schedule.id, {
        source_line_id: sourceLineId,
        quantity: draftQuantities[sourceLineId],
      }),
    );
  }

  async function removeSource(sourceLineId: string) {
    if (!schedule) return;
    await run(() => emergencyApi.removeSource(schedule.id, sourceLineId, "Исключено из экстренного расписания"));
  }

  async function addProduct() {
    if (!schedule || !addDraft.product_id) return;
    await run(async () => {
      const next = await emergencyApi.add(schedule.id, addDraft);
      setAddDraft((current) => ({ ...current, quantity: 1 }));
      return next;
    });
  }

  async function updateItem(lineId: string) {
    if (!schedule) return;
    await run(() => emergencyApi.update(schedule.id, lineId, { quantity: draftQuantities[lineId] }));
  }

  async function restoreItem(lineId: string) {
    if (!schedule) return;
    await run(() => emergencyApi.restore(schedule.id, lineId));
  }

  const backPath = order?.workshop_folder_id
    ? `/workshops/${order.workshop_folder_id}/orders/${order.order_id}`
    : "/orders/current";

  return (
    <ConsoleShell
      title="Экстренное расписание"
      subtitle="Приоритетный слой поверх основной заявки. Исходные позиции и количества не изменяются."
      actions={
        <div className="order-toolbar">
          <Link className="button-link" to={backPath}><ArrowLeft size={17} /> К заявке</Link>
          <button type="button" onClick={() => void reload()} disabled={loading || saving}><RefreshCw size={17} /> Обновить</button>
        </div>
      }
    >
      {loading ? <div className="empty-state">Загрузка...</div> : error && !order ? <div className="empty-state">{error}</div> : null}
      {error && order && <p className="error-text order-action-error">{error}</p>}

      {order && !schedule && (
        <section className="emergency-activation-card">
          <AlertTriangle size={42} />
          <div>
            <p className="eyebrow">Режим ещё не включён</p>
            <h2>Перевести заявку в экстренную работу</h2>
            <p>После включения изменения будут видны исполнителю над основной очередью, а каждое действие попадёт в журнал.</p>
          </div>
          <label>
            Причина перехода
            <textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={3} placeholder="Например: срочный дополнительный заказ" />
          </label>
          <button className="danger emergency-activate" type="button" onClick={() => void activate()} disabled={saving || reason.trim().length < 3}>
            <AlertTriangle size={18} /> Включить экстренный режим
          </button>
        </section>
      )}

      {schedule && (
        <div className="emergency-page">
          <section className="emergency-banner">
            <AlertTriangle size={30} />
            <div>
              <strong>Экстренный режим активен</strong>
              <span>{schedule.reason}</span>
              <small>{schedule.created_by_name ?? "Администратор"} · {new Date(schedule.created_at).toLocaleString("ru-RU")}</small>
            </div>
          </section>

          <section className="editor-card emergency-add-card">
            <div className="pane-heading"><div><p className="eyebrow">Приоритет № 1</p><h2>Добавить новую продукцию</h2></div></div>
            <div className="emergency-add-grid">
              <label>Продукция<select value={addDraft.product_id} onChange={(event) => setAddDraft((current) => ({ ...current, product_id: event.target.value }))}>
                {products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
              </select></label>
              <label>Количество{addUnit ? `, ${YIELD_UNIT_LABELS[addUnit]}` : ""}<input type="number" min={0} step={yieldStep(addUnit)} value={addDraft.quantity} onChange={(event) => setAddDraft((current) => ({ ...current, quantity: Number(event.target.value) }))} /></label>
              <label>Время<input type="time" value={addDraft.due_time} onChange={(event) => setAddDraft((current) => ({ ...current, due_time: event.target.value }))} /></label>
              <button className="primary" type="button" onClick={() => void addProduct()} disabled={saving || !addDraft.product_id || !isValidYieldQuantity(addDraft.quantity, addUnit)}><Plus size={17} /> Добавить поверх заявки</button>
            </div>
          </section>

          {schedule.items.some((item) => item.action === "add") && (
            <section className="editor-card">
              <div className="pane-heading"><div><p className="eyebrow">Экстренные добавления</p><h2>Новые позиции</h2></div></div>
              <div className="emergency-item-list">
                {schedule.items.filter((item) => item.action === "add").map((item) => (
                  <article key={item.id} className="emergency-item-row">
                    <div><strong>{item.product_name_raw}</strong><small>{item.due_time.slice(0, 5)} · всегда перед основной очередью</small></div>
                    <input aria-label={`Количество ${item.product_name_raw}`} type="number" min={0} step={yieldStep(item.unit)} value={draftQuantities[item.id] ?? item.quantity} onChange={(event) => setDraftQuantities((current) => ({ ...current, [item.id]: Number(event.target.value) }))} />
                    <button type="button" onClick={() => void updateItem(item.id)} disabled={saving || item.status !== "pending"}><Save size={16} /> Сохранить</button>
                    <button className="danger" type="button" onClick={() => void restoreItem(item.id)} disabled={saving || item.status !== "pending"}><Trash2 size={16} /> Убрать</button>
                  </article>
                ))}
              </div>
            </section>
          )}

          <section className="editor-card">
            <div className="pane-heading"><div><p className="eyebrow">Основная заявка</p><h2>Изменить количество или исключить</h2></div></div>
            <div className="emergency-source-list">
              {schedule.source_lines.map((line) => {
                const overlay = overlayBySource.get(line.id);
                const locked = line.status !== "pending" || (!!overlay && overlay.status !== "pending");
                return (
                  <article key={line.id} className={`emergency-source-row${overlay?.action === "remove" ? " removed" : ""}`}>
                    <div className="emergency-source-title">
                      <strong>{line.product_name_raw}</strong>
                      <small>{line.due_time.slice(0, 5)} · в основной заявке: {formatYield(line.quantity, line.unit ?? "pcs")}</small>
                      {locked && <span className="status-badge">Уже начата — изменение заблокировано</span>}
                      {overlay?.action === "replace" && <span className="emergency-chip">Экстренно: {formatYield(overlay.quantity, overlay.unit ?? "pcs")}</span>}
                      {overlay?.action === "remove" && <span className="emergency-chip">Исключена</span>}
                    </div>
                    {overlay?.action === "remove" ? (
                      <button type="button" onClick={() => void restoreItem(overlay.id)} disabled={saving || overlay.status !== "pending"}><RotateCcw size={16} /> Вернуть</button>
                    ) : (
                      <>
                        <label>Новое количество<input type="number" min={0} step={yieldStep(line.unit)} value={draftQuantities[line.id] ?? line.quantity} onChange={(event) => setDraftQuantities((current) => ({ ...current, [line.id]: Number(event.target.value) }))} disabled={locked} /></label>
                        <button type="button" onClick={() => void replaceSource(line.id)} disabled={saving || locked || !isValidYieldQuantity(draftQuantities[line.id] ?? line.quantity, line.unit)}><Save size={16} /> Применить</button>
                        <button className="danger" type="button" onClick={() => void removeSource(line.id)} disabled={saving || locked}><Trash2 size={16} /> Исключить</button>
                        {overlay && <button type="button" onClick={() => void restoreItem(overlay.id)} disabled={saving || overlay.status !== "pending"}><RotateCcw size={16} /> Сбросить</button>}
                      </>
                    )}
                  </article>
                );
              })}
            </div>
          </section>
        </div>
      )}
    </ConsoleShell>
  );
}
