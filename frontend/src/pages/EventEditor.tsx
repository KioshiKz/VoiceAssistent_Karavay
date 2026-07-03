import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { eventsApi } from "../api/endpoints";
import type { EventTemplateOut, EventType } from "../api/types";
import { useDialog } from "../components/DialogProvider";

const EVENT_TYPE_LABELS: Record<EventType, string> = {
  timer: "Таймер",
  weight_check: "Проверка весов",
  phrase_confirmation: "Подтверждение фразой",
};

export function EventEditor() {
  const { eventId } = useParams();
  const navigate = useNavigate();
  const [event, setEvent] = useState<EventTemplateOut | null>(null);
  const [saving, setSaving] = useState(false);
  const { alertMessage, confirmAction } = useDialog();

  useEffect(() => {
    if (!eventId) return;
    eventsApi.get(eventId).then(setEvent);
  }, [eventId]);

  if (!event) return <div className="editor-page">Загрузка...</div>;

  async function save() {
    if (!event) return;
    setSaving(true);
    try {
      const updated = await eventsApi.update(event.id, {
        name: event.name,
        description: event.description,
        event_type: event.event_type,
        is_active: event.is_active,
      });
      setEvent(updated);
      alertMessage("Сохранено");
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!event) return;
    if (!(await confirmAction("Удалить событие?"))) return;
    try {
      await eventsApi.remove(event.id);
      navigate(`/files/${event.folder_id}`);
    } catch {
      alertMessage("Нельзя удалить: событие используется в рецептуре. Деактивируйте вместо удаления.");
    }
  }

  return (
    <div className="editor-page">
      <Link to={`/files/${event.folder_id}`}>← К папке</Link>
      <h2>Событие</h2>

      <div className="editor-field">
        <label>Название</label>
        <input value={event.name} onChange={(e) => setEvent({ ...event, name: e.target.value })} />
      </div>

      <div className="editor-field">
        <label>Описание</label>
        <textarea
          value={event.description ?? ""}
          onChange={(e) => setEvent({ ...event, description: e.target.value })}
        />
      </div>

      <div className="editor-field">
        <label>Тип события</label>
        <select
          value={event.event_type}
          onChange={(e) => setEvent({ ...event, event_type: e.target.value as EventType })}
        >
          {Object.entries(EVENT_TYPE_LABELS).map(([k, label]) => (
            <option key={k} value={k}>
              {label}
            </option>
          ))}
        </select>
      </div>

      <p style={{ color: "#888", fontSize: 13 }}>
        Параметры этого события (время, вес, фраза) задаются в шаге рецептуры конкретной продукции, а не здесь.
      </p>

      <div className="editor-field">
        <label>
          <input
            type="checkbox"
            checked={event.is_active}
            onChange={(e) => setEvent({ ...event, is_active: e.target.checked })}
          />{" "}
          Активен
        </label>
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <button className="primary" onClick={save} disabled={saving}>
          Сохранить
        </button>
        <button onClick={remove}>Удалить</button>
      </div>
    </div>
  );
}
