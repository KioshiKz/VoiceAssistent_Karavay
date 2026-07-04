import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Save, Trash2 } from "lucide-react";
import { eventsApi } from "../api/endpoints";
import type { EventTemplateOut, EventType } from "../api/types";
import { useDialog } from "../components/DialogProvider";
import { FileWorkspaceShell } from "../components/FileWorkspaceShell";

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

  if (!event) {
    return (
      <FileWorkspaceShell title="Событие" subtitle="Загрузка карточки события." currentFolderId={null}>
        <div className="empty-state">Загрузка...</div>
      </FileWorkspaceShell>
    );
  }

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
      alertMessage("Нельзя удалить событие: оно используется в рецептуре. Деактивируйте его вместо удаления.");
    }
  }

  return (
    <FileWorkspaceShell
      title="Событие"
      subtitle="Шаблон производственного события для рецептур."
      currentFolderId={event.folder_id}
    >
      <div className="editor-page file-editor-inner">
        <Link to={`/files/${event.folder_id}`}>← К папке</Link>

        <section className="editor-card">
          <div className="pane-heading">
            <div>
              <p className="eyebrow">Карточка</p>
              <h2>{event.name}</h2>
            </div>
            <div className="action-row">
              <button className="primary" type="button" onClick={save} disabled={saving}>
                <Save size={17} />
                {saving ? "Сохранение..." : "Сохранить"}
              </button>
              <button className="danger" type="button" onClick={remove}>
                <Trash2 size={17} />
                Удалить
              </button>
            </div>
          </div>

          <label className="editor-field">
            Название
            <input value={event.name} onChange={(changeEvent) => setEvent({ ...event, name: changeEvent.target.value })} />
          </label>

          <label className="editor-field">
            Описание
            <textarea
              value={event.description ?? ""}
              onChange={(changeEvent) => setEvent({ ...event, description: changeEvent.target.value })}
            />
          </label>

          <label className="editor-field">
            Тип события
            <select
              value={event.event_type}
              onChange={(changeEvent) => setEvent({ ...event, event_type: changeEvent.target.value as EventType })}
            >
              {Object.entries(EVENT_TYPE_LABELS).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <div className="system-role-note">
            Параметры события: длительность, целевой вес, допуск или фраза подтверждения задаются в шаге рецептуры
            конкретной продукции.
          </div>

          <label className="checkbox-line">
            <input
              type="checkbox"
              checked={event.is_active}
              onChange={(changeEvent) => setEvent({ ...event, is_active: changeEvent.target.checked })}
            />
            Активно
          </label>
        </section>
      </div>
    </FileWorkspaceShell>
  );
}
