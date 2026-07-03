import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ingredientsApi } from "../api/endpoints";
import type { IngredientOut, MeasureType, UsedInProductOut } from "../api/types";
import { useDialog } from "../components/DialogProvider";

const MEASURE_LABELS: Record<MeasureType, string> = {
  weight: "Вес",
  volume: "Объём",
  time: "Время",
  temperature: "Температура",
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
    ingredientsApi.get(ingredientId).then((i) => {
      setIngredient(i);
      setContainerWeightsText((i.allowed_container_weights_g ?? []).join(", "));
    });
    ingredientsApi.usedIn(ingredientId).then(setUsedIn);
  }, [ingredientId]);

  if (!ingredient) return <div className="editor-page">Загрузка...</div>;

  async function save() {
    if (!ingredient) return;
    setSaving(true);
    try {
      const weights = containerWeightsText
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .map(Number)
        .filter((n) => !Number.isNaN(n));
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
      alertMessage("Нельзя удалить: ингредиент используется в рецептуре. Деактивируйте вместо удаления.");
    }
  }

  return (
    <div className="editor-page">
      <Link to={`/files/${ingredient.folder_id}`}>← К папке</Link>
      <h2>Ингредиент</h2>

      <div className="editor-field">
        <label>Название</label>
        <input value={ingredient.name} onChange={(e) => setIngredient({ ...ingredient, name: e.target.value })} />
      </div>

      <div className="editor-field">
        <label>Мера измерения</label>
        <select
          value={ingredient.measure_type}
          onChange={(e) => setIngredient({ ...ingredient, measure_type: e.target.value as MeasureType })}
        >
          {Object.entries(MEASURE_LABELS).map(([k, label]) => (
            <option key={k} value={k}>
              {label}
            </option>
          ))}
        </select>
      </div>

      <div className="editor-field">
        <label>Описание</label>
        <textarea
          value={ingredient.description ?? ""}
          onChange={(e) => setIngredient({ ...ingredient, description: e.target.value })}
        />
      </div>

      <div className="editor-field">
        <label>Допустимые веса тары хранения (через запятую, в граммах)</label>
        <input value={containerWeightsText} onChange={(e) => setContainerWeightsText(e.target.value)} />
      </div>

      <div className="editor-field">
        <label>
          <input
            type="checkbox"
            checked={ingredient.is_active}
            onChange={(e) => setIngredient({ ...ingredient, is_active: e.target.checked })}
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

      <h3 style={{ marginTop: 32 }}>Используется в продукции</h3>
      {usedIn.length === 0 ? (
        <p style={{ color: "#888" }}>Пока нигде не используется.</p>
      ) : (
        <ul>
          {usedIn.map((u) => (
            <li key={u.product_id}>
              <Link to={`/products/${u.product_id}`}>{u.product_name}</Link>{" "}
              <span style={{ color: "#888" }}>({u.folder_path})</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
