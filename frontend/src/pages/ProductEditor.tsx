import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { eventsApi, ingredientsApi, productsApi } from "../api/endpoints";
import type { EventTemplateOut, IngredientOut, ProductDetailOut } from "../api/types";
import { RecipeStepList } from "../components/RecipeStepList";
import { UnitQuantityInput } from "../components/UnitQuantityInput";
import { useDialog } from "../components/DialogProvider";

export function ProductEditor() {
  const { productId } = useParams();
  const { alertMessage } = useDialog();
  const [product, setProduct] = useState<ProductDetailOut | null>(null);
  const [ingredients, setIngredients] = useState<IngredientOut[]>([]);
  const [events, setEvents] = useState<EventTemplateOut[]>([]);

  const [addMode, setAddMode] = useState<"ingredient" | "event" | null>(null);
  const [selectedIngredientId, setSelectedIngredientId] = useState("");
  const [ingredientQty, setIngredientQty] = useState(0);
  const [selectedEventId, setSelectedEventId] = useState("");
  const [eventParams, setEventParams] = useState<Record<string, number | string>>({});

  function reload() {
    if (!productId) return;
    productsApi.get(productId).then((p) => {
      setProduct(p);
      ingredientsApi.listInFolder(p.folder_id).then(setIngredients);
      eventsApi.listInFolder(p.folder_id).then(setEvents);
    });
  }

  useEffect(reload, [productId]);

  if (!product) return <div className="editor-page">Загрузка...</div>;

  async function saveHeader() {
    if (!product) return;
    await productsApi.update(product.id, { name: product.name, base_quantity: product.base_quantity });
    alertMessage("Сохранено");
  }

  const selectedIngredient = ingredients.find((i) => i.id === selectedIngredientId) ?? null;
  const selectedEvent = events.find((e) => e.id === selectedEventId) ?? null;

  async function addIngredientStep() {
    if (!product || !selectedIngredientId) return;
    await productsApi.createStep(product.id, {
      step_type: "ingredient",
      order_index: product.steps.length,
      ingredient_id: selectedIngredientId,
      quantity_canonical: ingredientQty,
    });
    setAddMode(null);
    setSelectedIngredientId("");
    setIngredientQty(0);
    reload();
  }

  async function addEventStep() {
    if (!product || !selectedEventId || !selectedEvent) return;
    let params: Record<string, unknown> = {};
    if (selectedEvent.event_type === "timer") {
      params = { duration_seconds: Number(eventParams.duration_seconds ?? 0) };
    } else if (selectedEvent.event_type === "weight_check") {
      params = {
        target_weight_g: Number(eventParams.target_weight_g ?? 0),
        tolerance_g: Number(eventParams.tolerance_g ?? 0),
      };
    } else if (selectedEvent.event_type === "phrase_confirmation") {
      params = { phrase: String(eventParams.phrase ?? "") };
    }
    await productsApi.createStep(product.id, {
      step_type: "event",
      order_index: product.steps.length,
      event_template_id: selectedEventId,
      event_params: params,
    });
    setAddMode(null);
    setSelectedEventId("");
    setEventParams({});
    reload();
  }

  async function moveStep(stepId: string, direction: -1 | 1) {
    if (!product) return;
    const ids = product.steps.map((s) => s.id);
    const idx = ids.indexOf(stepId);
    const target = idx + direction;
    if (target < 0 || target >= ids.length) return;
    [ids[idx], ids[target]] = [ids[target], ids[idx]];
    await productsApi.reorderSteps(product.id, ids);
    reload();
  }

  async function deleteStep(stepId: string) {
    if (!product) return;
    await productsApi.deleteStep(product.id, stepId);
    reload();
  }

  return (
    <div className="editor-page">
      <Link to={`/files/${product.folder_id}`}>← К папке</Link>
      <h2>Продукция</h2>

      <div className="editor-field">
        <label>Название</label>
        <input value={product.name} onChange={(e) => setProduct({ ...product, name: e.target.value })} />
      </div>
      <div className="editor-field">
        <label>Базовое количество (шт)</label>
        <input
          type="number"
          value={product.base_quantity}
          onChange={(e) => setProduct({ ...product, base_quantity: Number(e.target.value) })}
        />
      </div>
      <button className="primary" onClick={saveHeader}>
        Сохранить
      </button>

      <h3 style={{ marginTop: 24 }}>Рецептура</h3>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button onClick={() => setAddMode("ingredient")}>+ Добавить ингредиент</button>
        <button onClick={() => setAddMode("event")}>+ Добавить событие</button>
      </div>

      {addMode === "ingredient" && (
        <div style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 12 }}>
          <select value={selectedIngredientId} onChange={(e) => setSelectedIngredientId(e.target.value)}>
            <option value="">Выберите ингредиент</option>
            {ingredients.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name}
              </option>
            ))}
          </select>
          {selectedIngredient && (
            <div style={{ marginTop: 8 }}>
              <UnitQuantityInput
                measureType={selectedIngredient.measure_type}
                valueCanonical={ingredientQty}
                onChange={setIngredientQty}
              />
            </div>
          )}
          <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
            <button className="primary" onClick={addIngredientStep} disabled={!selectedIngredientId}>
              Добавить
            </button>
            <button onClick={() => setAddMode(null)}>Отмена</button>
          </div>
        </div>
      )}

      {addMode === "event" && (
        <div style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 12 }}>
          <select value={selectedEventId} onChange={(e) => setSelectedEventId(e.target.value)}>
            <option value="">Выберите событие</option>
            {events.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name}
              </option>
            ))}
          </select>
          {selectedEvent?.event_type === "timer" && (
            <div style={{ marginTop: 8 }}>
              Длительность (сек):{" "}
              <input
                type="number"
                value={Number(eventParams.duration_seconds ?? 0)}
                onChange={(e) => setEventParams({ ...eventParams, duration_seconds: e.target.value })}
              />
            </div>
          )}
          {selectedEvent?.event_type === "weight_check" && (
            <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
              Целевой вес (г):{" "}
              <input
                type="number"
                value={Number(eventParams.target_weight_g ?? 0)}
                onChange={(e) => setEventParams({ ...eventParams, target_weight_g: e.target.value })}
              />
              Допуск (г):{" "}
              <input
                type="number"
                value={Number(eventParams.tolerance_g ?? 0)}
                onChange={(e) => setEventParams({ ...eventParams, tolerance_g: e.target.value })}
              />
            </div>
          )}
          {selectedEvent?.event_type === "phrase_confirmation" && (
            <div style={{ marginTop: 8 }}>
              Фраза:{" "}
              <input
                value={String(eventParams.phrase ?? "")}
                onChange={(e) => setEventParams({ ...eventParams, phrase: e.target.value })}
              />
            </div>
          )}
          <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
            <button className="primary" onClick={addEventStep} disabled={!selectedEventId}>
              Добавить
            </button>
            <button onClick={() => setAddMode(null)}>Отмена</button>
          </div>
        </div>
      )}

      <RecipeStepList
        steps={product.steps}
        onMoveUp={(id) => moveStep(id, -1)}
        onMoveDown={(id) => moveStep(id, 1)}
        onDelete={deleteStep}
      />
    </div>
  );
}
