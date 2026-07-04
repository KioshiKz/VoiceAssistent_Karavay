import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Save, Trash2 } from "lucide-react";
import { ingredientsApi } from "../api/endpoints";
import type { IngredientOut, MeasureType, UsedInProductOut } from "../api/types";
import { useDialog } from "../components/DialogProvider";
import { FileWorkspaceShell } from "../components/FileWorkspaceShell";

const MEASURE_LABELS: Record<MeasureType, string> = {
  weight: "Вес",
  volume: "Объём",
  time: "Время",
  temperature: "Температура",
  count: "Штуки",
};

export function IngredientEditor() {
  const { ingredientId } = useParams();
  const navigate = useNavigate();
  const [ingredient, setIngredient] = useState<IngredientOut | null>(null);
  const [usedIn, setUsedIn] = useState<UsedInProductOut[]>([]);
  const [containerWeightsText, setContainerWeightsText] = useState("");
  const [saving, setSaving] = useState(false);
  const { alertMessage, confirmAction } = useDialog();

  useEffect(() => {
    if (!ingredientId) return;
    ingredientsApi.get(ingredientId).then((nextIngredient) => {
      setIngredient(nextIngredient);
      setContainerWeightsText((nextIngredient.allowed_container_weights_g ?? []).join(", "));
    });
    ingredientsApi.usedIn(ingredientId).then(setUsedIn);
  }, [ingredientId]);

  if (!ingredient) {
    return (
      <FileWorkspaceShell title="Ингредиент" subtitle="Загрузка карточки ингредиента." currentFolderId={null}>
        <div className="empty-state">Загрузка...</div>
      </FileWorkspaceShell>
    );
  }

  async function save() {
    if (!ingredient) return;
    setSaving(true);
    try {
      const weights = containerWeightsText
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean)
        .map(Number)
        .filter((item) => !Number.isNaN(item));
      const updated = await ingredientsApi.update(ingredient.id, {
        name: ingredient.name,
        measure_type: ingredient.measure_type,
        description: ingredient.description,
        allowed_container_weights_g: weights.length ? weights : null,
        is_active: ingredient.is_active,
      });
      setIngredient(updated);
      alertMessage("Сохранено");
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!ingredient) return;
    if (!(await confirmAction("Удалить ингредиент?"))) return;
    try {
      await ingredientsApi.remove(ingredient.id);
      navigate(`/files/${ingredient.folder_id}`);
    } catch {
      alertMessage("Нельзя удалить ингредиент: он используется в рецептуре. Деактивируйте его вместо удаления.");
    }
  }

  return (
    <FileWorkspaceShell
      title="Ингредиент"
      subtitle="Карточка сырья, единицы измерения и ограничения тары."
      currentFolderId={ingredient.folder_id}
    >
      <div className="editor-page file-editor-inner">
        <Link to={`/files/${ingredient.folder_id}`}>← К папке</Link>

        <section className="editor-card">
          <div className="pane-heading">
            <div>
              <p className="eyebrow">Карточка</p>
              <h2>{ingredient.name}</h2>
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
            <input value={ingredient.name} onChange={(event) => setIngredient({ ...ingredient, name: event.target.value })} />
          </label>

          <label className="editor-field">
            Мера измерения
            <select
              value={ingredient.measure_type}
              onChange={(event) => setIngredient({ ...ingredient, measure_type: event.target.value as MeasureType })}
            >
              {Object.entries(MEASURE_LABELS).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <label className="editor-field">
            Описание
            <textarea
              value={ingredient.description ?? ""}
              onChange={(event) => setIngredient({ ...ingredient, description: event.target.value })}
            />
          </label>

          <label className="editor-field">
            Допустимые веса тары хранения, г
            <input value={containerWeightsText} onChange={(event) => setContainerWeightsText(event.target.value)} />
          </label>

          <label className="checkbox-line">
            <input
              type="checkbox"
              checked={ingredient.is_active}
              onChange={(event) => setIngredient({ ...ingredient, is_active: event.target.checked })}
            />
            Активен
          </label>
        </section>

        <section className="editor-card">
          <div>
            <p className="eyebrow">Связи</p>
            <h2>Используется в продукции</h2>
          </div>
          {usedIn.length === 0 ? (
            <p className="muted">Пока нигде не используется.</p>
          ) : (
            <div className="summary-list">
              {usedIn.map((item) => (
                <span key={item.product_id}>
                  <Link to={`/products/${item.product_id}`}>{item.product_name}</Link>
                  <small>{item.folder_path}</small>
                </span>
              ))}
            </div>
          )}
        </section>
      </div>
    </FileWorkspaceShell>
  );
}
