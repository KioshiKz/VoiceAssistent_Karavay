import { useEffect, useMemo, useState } from "react";
import { CalendarClock, Pin, RotateCcw, X } from "lucide-react";
import { foldersApi, ordersApi } from "../api/endpoints";
import type { CurrentOrderOut, FolderOut, OrderSummaryOut } from "../api/types";
import { useAuth } from "../auth/AuthContext";

interface CurrentOrderSelectionProps {
  currentOrder: CurrentOrderOut | null;
  onChanged: (currentOrder: CurrentOrderOut) => void | Promise<unknown>;
}

function localDateValue() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function formatDate(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "long", year: "numeric" }).format(
    new Date(year, month - 1, day),
  );
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

function statusLabel(status: OrderSummaryOut["status"]) {
  if (status === "pending") return "ожидает";
  if (status === "in_progress") return "в работе";
  return "завершена";
}

export function CurrentOrderSelection({ currentOrder, onChanged }: CurrentOrderSelectionProps) {
  const { hasGlobal } = useAuth();
  const canSelectCurrent = hasGlobal("orders.select_current");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [workshops, setWorkshops] = useState<FolderOut[]>([]);
  const [workshopId, setWorkshopId] = useState("");
  const [executionDate, setExecutionDate] = useState(localDateValue);
  const [candidates, setCandidates] = useState<OrderSummaryOut[]>([]);
  const [selectedOrderId, setSelectedOrderId] = useState("");
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const currentWorkshopId =
    currentOrder?.workshop_folder_id ??
    currentOrder?.lines.find((line) => line.workshop_folder_id)?.workshop_folder_id ??
    null;
  const isManual = currentOrder?.selection_mode === "manual";

  const sortedCandidates = useMemo(
    () =>
      [...candidates].sort(
        (left, right) =>
          right.execution_date.localeCompare(left.execution_date) || left.uploaded_at.localeCompare(right.uploaded_at),
      ),
    [candidates],
  );

  useEffect(() => {
    if (!dialogOpen || !workshopId || !executionDate) {
      setCandidates([]);
      setLoadingCandidates(false);
      return;
    }

    let active = true;
    setLoadingCandidates(true);
    setDialogError(null);
    ordersApi
      .currentCandidates(workshopId, executionDate)
      .then((items) => {
        if (!active) return;
        setCandidates(items);
        const currentIsCandidate = items.some((item) => item.id === currentOrder?.order_id);
        setSelectedOrderId(currentIsCandidate ? currentOrder?.order_id ?? "" : items[0]?.id ?? "");
      })
      .catch(() => {
        if (!active) return;
        setCandidates([]);
        setSelectedOrderId("");
        setDialogError("Не удалось загрузить заявки для выбранного цеха и даты.");
      })
      .finally(() => {
        if (active) setLoadingCandidates(false);
      });

    return () => {
      active = false;
    };
  }, [currentOrder?.order_id, dialogOpen, executionDate, workshopId]);

  if (!canSelectCurrent) return null;

  async function openDialog() {
    setDialogError(null);
    setActionError(null);
    setExecutionDate(currentOrder?.execution_date ?? localDateValue());
    setWorkshopId(currentWorkshopId ?? "");
    setSelectedOrderId(currentOrder?.order_id ?? "");
    setDialogOpen(true);

    try {
      const visibleFolders = await foldersApi.tree();
      const roots = visibleFolders
        .filter((folder) => folder.parent_id === null)
        .sort((left, right) => left.name.localeCompare(right.name, "ru"));
      setWorkshops(roots);
      if (!currentWorkshopId && roots[0]) setWorkshopId(roots[0].id);
    } catch {
      setWorkshops([]);
      setDialogError("Не удалось загрузить доступные цеха.");
    }
  }

  async function applySelection() {
    const selected = candidates.find((candidate) => candidate.id === selectedOrderId);
    if (!selected?.workshop_folder_id) return;
    setSaving(true);
    setDialogError(null);
    try {
      const updated = await ordersApi.setCurrentSelection(
        selected.workshop_folder_id,
        selected.execution_date,
        selected.id,
      );
      setDialogOpen(false);
      await onChanged(updated);
    } catch {
      setDialogError("Не удалось сделать заявку текущей.");
    } finally {
      setSaving(false);
    }
  }

  async function resetSelection() {
    if (!currentOrder || !currentWorkshopId) return;
    setSaving(true);
    setActionError(null);
    try {
      const updated = await ordersApi.setCurrentSelection(currentWorkshopId, currentOrder.execution_date, null);
      await onChanged(updated);
    } catch {
      setActionError("Не удалось вернуть автоматический выбор.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <section className="current-order-selection-panel">
        <div className="current-order-selection-copy">
          <p className="eyebrow">Выбор актуальной заявки</p>
          <div className="current-order-selection-title">
            <h2>{isManual ? "Ручной режим" : "Автоматический режим"}</h2>
            <span className={`status-badge${isManual ? " current-order-manual-badge" : " success"}`}>
              {isManual ? "закреплена вручную" : "автовыбор"}
            </span>
          </div>
          <p>
            {currentOrder
              ? isManual
                ? `Заявка за ${formatDate(currentOrder.execution_date)} выбрана вручную для цеха «${currentOrder.workshop_folder_name ?? "без названия"}».`
                : `Выбрана самая старая доступная заявка за ${formatDate(currentOrder.execution_date)} в цехе «${currentOrder.workshop_folder_name ?? "без названия"}».`
              : "Выберите цех и дату, чтобы назначить актуальную заявку."}
          </p>
          {isManual && currentOrder?.selected_by_name && (
            <small>
              Выбрал: {currentOrder.selected_by_name}
              {currentOrder.selected_at ? `, ${new Date(currentOrder.selected_at).toLocaleString("ru-RU")}` : ""}
            </small>
          )}
          {actionError && <span className="error-text">{actionError}</span>}
        </div>
        <div className="current-order-selection-actions">
          {isManual && (
            <button type="button" onClick={() => void resetSelection()} disabled={saving || !currentWorkshopId}>
              <RotateCcw size={17} />
              Вернуть автовыбор для этого цеха
            </button>
          )}
          <button type="button" className="primary" onClick={() => void openDialog()} disabled={saving}>
            <Pin size={17} />
            Выбрать вручную
          </button>
        </div>
      </section>

      {dialogOpen && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => !saving && setDialogOpen(false)}>
          <div
            className="modal-card current-order-selection-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="current-order-selection-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h2 id="current-order-selection-title">Выбрать актуальную заявку</h2>
                <p>Ручной выбор действует только для указанных цеха и даты.</p>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={() => setDialogOpen(false)}
                disabled={saving}
                title="Закрыть"
              >
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <div className="current-order-context-fields">
                <label className="modal-field">
                  Цех
                  <select value={workshopId} onChange={(event) => setWorkshopId(event.target.value)} disabled={saving}>
                    <option value="" disabled>
                      Выберите цех
                    </option>
                    {workshops.map((workshop) => (
                      <option key={workshop.id} value={workshop.id}>
                        {workshop.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="modal-field">
                  Дата текущей очереди
                  <input type="date" value={executionDate} disabled />
                  <small>Заявку на другую дату можно назначить из её карточки.</small>
                </label>
              </div>

              {loadingCandidates ? (
                <div className="empty-state">Загрузка заявок...</div>
              ) : dialogError ? (
                <p className="error-text current-order-selection-error">{dialogError}</p>
              ) : sortedCandidates.length === 0 ? (
                <div className="empty-state">Для выбранных цеха и даты активных заявок нет.</div>
              ) : (
                <div className="current-order-candidates">
                  {sortedCandidates.map((candidate) => (
                    <label
                      className={`current-order-candidate${selectedOrderId === candidate.id ? " selected" : ""}`}
                      key={candidate.id}
                    >
                      <input
                        type="radio"
                        name="current-order"
                        value={candidate.id}
                        checked={selectedOrderId === candidate.id}
                        onChange={() => setSelectedOrderId(candidate.id)}
                        disabled={saving}
                      />
                      <span>
                        <strong>Заявка за {formatDate(candidate.execution_date)}</strong>
                        <small>
                          {candidate.source_filename ? "Загружена" : "Создана"} {formatTime(candidate.uploaded_at)} ·{" "}
                          {candidate.total_lines} позиций · {statusLabel(candidate.status)}
                        </small>
                      </span>
                      {candidate.id === currentOrder?.order_id && <span className="status-badge success">Сейчас</span>}
                    </label>
                  ))}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button type="button" onClick={() => setDialogOpen(false)} disabled={saving}>
                Отмена
              </button>
              <button
                type="button"
                className="primary"
                onClick={() => void applySelection()}
                disabled={saving || !selectedOrderId || loadingCandidates}
              >
                <CalendarClock size={17} />
                {saving ? "Сохранение..." : "Сделать текущей"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
