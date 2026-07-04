import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { BellRing, Plus, Save, Wheat, Workflow, X } from "lucide-react";
import { eventsApi, ingredientsApi, productsApi } from "../api/endpoints";
import type { EventTemplateOut, IngredientOut, ProductDetailOut } from "../api/types";
import { RecipeStepList } from "../components/RecipeStepList";
import { UnitQuantityInput } from "../components/UnitQuantityInput";
import { useDialog } from "../components/DialogProvider";
import { FileWorkspaceShell } from "../components/FileWorkspaceShell";

type AddMode = "ingredient" | "event" | "ingredient_event" | null;

export function ProductEditor() {
  const { productId } = useParams();
  const { alertMessage } = useDialog();
  const [product, setProduct] = useState<ProductDetailOut | null>(null);
  const [ingredients, setIngredients] = useState<IngredientOut[]>([]);
  const [events, setEvents] = useState<EventTemplateOut[]>([]);

  const [addMode, setAddMode] = useState<AddMode>(null);
  const [selectedIngredientId, setSelectedIngredientId] = useState("");
  const [ingredientQty, setIngredientQty] = useState(0);
  const [selectedEventId, setSelectedEventId] = useState("");
  const [eventParams, setEventParams] = useState<Record<string, number | string>>({});

  function reload() {
    if (!productId) return;
    productsApi.get(productId).then((nextProduct) => {
      setProduct(nextProduct);
      ingredientsApi.listInFolder(nextProduct.folder_id).then(setIngredients);
      eventsApi.listInFolder(nextProduct.folder_id).then(setEvents);
    });
  }

  useEffect(reload, [productId]);

  if (!product) {
    return (
      <FileWorkspaceShell title="Продукция" subtitle="Загрузка карточки продукции." currentFolderId={null}>
        <div className="empty-state">Загрузка...</div>
      </FileWorkspaceShell>
    );
  }

  const selectedIngredient = ingredients.find((ingredient) => ingredient.id === selectedIngredientId) ?? null;
  const selectedEvent = events.find((event) => event.id === selectedEventId) ?? null;
  const needsIngredient = addMode === "ingredient" || addMode === "ingredient_event";
  const needsEvent = addMode === "event" || addMode === "ingredient_event";

  async function saveHeader() {
    if (!product) return;
    await productsApi.update(product.id, { name: product.name, base_quantity: product.base_quantity });
    alertMessage("Сохранено");
  }

  function openStepModal(mode: Exclude<AddMode, null>) {
    setAddMode(mode);
    setSelectedIngredientId("");
    setIngredientQty(0);
    setSelectedEventId("");
    setEventParams(mode === "ingredient_event" ? { start_phrase: "старт" } : {});
  }

  function closeStepModal() {
    setAddMode(null);
  }

  function buildEventParams() {
    if (!selectedEvent) return {};
    if (selectedEvent.event_type === "timer") {
      return {
        duration_seconds: Number(eventParams.duration_seconds ?? 0),
        start_phrase: String(eventParams.start_phrase ?? "старт"),
      };
    }
    if (selectedEvent.event_type === "weight_check") {
      return {
        target_weight_g: Number(eventParams.target_weight_g ?? 0),
        tolerance_g: Number(eventParams.tolerance_g ?? 0),
      };
    }
    if (selectedEvent.event_type === "phrase_confirmation") {
      return { phrase: String(eventParams.phrase ?? "") };
    }
    return {};
  }

  async function addIngredientStep() {
    if (!product || !selectedIngredientId) return;
    await productsApi.createStep(product.id, {
      step_type: "ingredient",
      order_index: product.steps.length,
      ingredient_id: selectedIngredientId,
      quantity_canonical: ingredientQty,
    });
    closeStepModal();
    reload();
  }

  async function addEventStep() {
    if (!product || !selectedEventId || !selectedEvent) return;
    await productsApi.createStep(product.id, {
      step_type: "event",
      order_index: product.steps.length,
      event_template_id: selectedEventId,
      event_params: buildEventParams(),
    });
    closeStepModal();
    reload();
  }

  async function addLinkedStep() {
    if (!product || !selectedIngredientId || !selectedEventId || !selectedEvent) return;
    await productsApi.createStep(product.id, {
      step_type: "ingredient_event",
      order_index: product.steps.length,
      ingredient_id: selectedIngredientId,
      quantity_canonical: ingredientQty,
      event_template_id: selectedEventId,
      event_params: buildEventParams(),
    });
    closeStepModal();
    reload();
  }

  async function moveStep(stepId: string, direction: -1 | 1) {
    if (!product) return;
    const ids = product.steps.map((step) => step.id);
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

  function submitStep() {
    if (addMode === "ingredient") return addIngredientStep();
    if (addMode === "event") return addEventStep();
    return addLinkedStep();
  }

  const submitDisabled =
    (needsIngredient && !selectedIngredientId) || (needsEvent && !selectedEventId) || (needsIngredient && !ingredientQty);

  return (
    <FileWorkspaceShell
      title="Продукция"
      subtitle="Карточка продукции и пошаговая рецептура."
      currentFolderId={product.folder_id}
    >
      <div className="editor-page file-editor-inner">
        <Link to={`/files/${product.folder_id}`}>← К папке</Link>

        <section className="editor-card">
          <div className="pane-heading">
            <div>
              <p className="eyebrow">Карточка</p>
              <h2>{product.name || "Новая продукция"}</h2>
            </div>
            <button className="primary" type="button" onClick={saveHeader}>
              <Save size={17} />
              Сохранить
            </button>
          </div>

          <label className="editor-field">
            Название
            <input value={product.name} onChange={(event) => setProduct({ ...product, name: event.target.value })} />
          </label>
          <label className="editor-field">
            Базовое количество, шт.
            <input
              type="number"
              value={product.base_quantity}
              onChange={(event) => setProduct({ ...product, base_quantity: Number(event.target.value) })}
            />
          </label>
        </section>

        <section className="editor-card">
          <div className="pane-heading">
            <div>
              <p className="eyebrow">Рецептура</p>
              <h2>Шаги приготовления</h2>
            </div>
            <div className="action-row">
              <button type="button" onClick={() => openStepModal("ingredient")}>
                <Wheat size={17} />
                Ингредиент
              </button>
              <button type="button" onClick={() => openStepModal("event")}>
                <BellRing size={17} />
                Событие
              </button>
              <button type="button" onClick={() => openStepModal("ingredient_event")}>
                <Workflow size={17} />
                Связанное
              </button>
            </div>
          </div>

          <RecipeStepList
            steps={product.steps}
            onMoveUp={(id) => moveStep(id, -1)}
            onMoveDown={(id) => moveStep(id, 1)}
            onDelete={deleteStep}
          />
        </section>
      </div>

      {addMode && (
        <div className="modal-backdrop" role="presentation" onMouseDown={closeStepModal}>
          <div className="modal-card" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>
                  {addMode === "ingredient"
                    ? "Добавить ингредиент"
                    : addMode === "event"
                      ? "Добавить событие"
                      : "Добавить связанное действие"}
                </h2>
                <p>Заполните параметры шага до добавления в рецептуру.</p>
              </div>
              <button className="icon-button" type="button" onClick={closeStepModal} title="Закрыть">
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              {needsIngredient && (
                <>
                  <label className="modal-field">
                    Ингредиент
                    <select value={selectedIngredientId} onChange={(event) => setSelectedIngredientId(event.target.value)}>
                      <option value="">Выберите ингредиент</option>
                      {ingredients.map((ingredient) => (
                        <option key={ingredient.id} value={ingredient.id}>
                          {ingredient.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  {selectedIngredient && (
                    <label className="modal-field">
                      Количество
                      <UnitQuantityInput
                        measureType={selectedIngredient.measure_type}
                        valueCanonical={ingredientQty}
                        onChange={setIngredientQty}
                      />
                    </label>
                  )}
                </>
              )}

              {needsEvent && (
                <>
                  <label className="modal-field">
                    Событие
                    <select value={selectedEventId} onChange={(event) => setSelectedEventId(event.target.value)}>
                      <option value="">Выберите событие</option>
                      {events.map((event) => (
                        <option key={event.id} value={event.id}>
                          {event.name}
                        </option>
                      ))}
                    </select>
                  </label>

                  {selectedEvent?.event_type === "timer" && (
                    <div className="modal-grid">
                      <label className="modal-field">
                        Длительность, секунд
                        <input
                          type="number"
                          value={Number(eventParams.duration_seconds ?? 0)}
                          onChange={(event) => setEventParams({ ...eventParams, duration_seconds: event.target.value })}
                        />
                      </label>
                      <label className="modal-field">
                        Кодовая фраза запуска
                        <input
                          value={String(eventParams.start_phrase ?? "старт")}
                          onChange={(event) => setEventParams({ ...eventParams, start_phrase: event.target.value })}
                        />
                      </label>
                    </div>
                  )}

                  {selectedEvent?.event_type === "weight_check" && (
                    <div className="modal-grid">
                      <label className="modal-field">
                        Целевой вес, г
                        <input
                          type="number"
                          value={Number(eventParams.target_weight_g ?? 0)}
                          onChange={(event) => setEventParams({ ...eventParams, target_weight_g: event.target.value })}
                        />
                      </label>
                      <label className="modal-field">
                        Допуск, г
                        <input
                          type="number"
                          value={Number(eventParams.tolerance_g ?? 0)}
                          onChange={(event) => setEventParams({ ...eventParams, tolerance_g: event.target.value })}
                        />
                      </label>
                    </div>
                  )}

                  {selectedEvent?.event_type === "phrase_confirmation" && (
                    <label className="modal-field">
                      Фраза подтверждения
                      <input
                        value={String(eventParams.phrase ?? "")}
                        onChange={(event) => setEventParams({ ...eventParams, phrase: event.target.value })}
                      />
                    </label>
                  )}
                </>
              )}
            </div>

            <div className="modal-footer">
              <button type="button" onClick={closeStepModal}>
                Отмена
              </button>
              <button className="primary" type="button" onClick={() => void submitStep()} disabled={submitDisabled}>
                <Plus size={17} />
                Добавить
              </button>
            </div>
          </div>
        </div>
      )}
    </FileWorkspaceShell>
  );
}
