import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type FormEvent, type MouseEvent as ReactMouseEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { BellRing, CheckCircle2, FolderPlus, PackagePlus, Pencil, Plus, Trash2, Wheat, XCircle } from "lucide-react";
import { eventsApi, foldersApi, ingredientsApi, productsApi } from "../api/endpoints";
import type { EventType, FolderContentOut, FolderOut, MeasureType } from "../api/types";
import { FolderTree } from "../components/FolderTree";
import { Breadcrumbs } from "../components/Breadcrumbs";
import { FolderContentGrid } from "../components/FolderContentGrid";
import { useAuth } from "../auth/AuthContext";
import { useDialog } from "../components/DialogProvider";
import { buildFolderTree } from "../utils/folderTree";
import { ConsoleShell } from "../components/ConsoleShell";
import { contentItemKey, type ContentSelectionItem } from "../utils/contentSelection";

type CreateKind = "folder" | "ingredient" | "product" | "event";

interface CreateFormState {
  name: string;
  description: string;
  measureType: MeasureType;
  containerWeights: string;
  baseQuantity: number;
  eventType: EventType;
  isActive: boolean;
}

const CREATE_TITLES: Record<CreateKind, { title: string; subtitle: string }> = {
  folder: { title: "Новая папка", subtitle: "Создайте раздел в текущей структуре." },
  ingredient: { title: "Новый ингредиент", subtitle: "Заполните карточку ингредиента сразу при создании." },
  product: { title: "Новая продукция", subtitle: "Создайте продукцию и перейдите к рецептуре." },
  event: { title: "Новое событие", subtitle: "Опишите производственное событие или контрольную точку." },
};

const MEASURE_OPTIONS: { value: MeasureType; label: string }[] = [
  { value: "weight", label: "Вес" },
  { value: "volume", label: "Объём" },
  { value: "time", label: "Время" },
  { value: "temperature", label: "Температура" },
  { value: "count", label: "Штуки" },
];

const EVENT_OPTIONS: { value: EventType; label: string }[] = [
  { value: "timer", label: "Таймер" },
  { value: "weight_check", label: "Проверка веса" },
  { value: "phrase_confirmation", label: "Подтверждение фразой" },
];

function initialCreateForm(): CreateFormState {
  return {
    name: "",
    description: "",
    measureType: "weight",
    containerWeights: "",
    baseQuantity: 100,
    eventType: "timer",
    isActive: true,
  };
}

function parseWeights(value: string) {
  const weights = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map(Number)
    .filter((item) => !Number.isNaN(item) && item > 0);
  return weights.length ? weights : null;
}

export function FileManager() {
  const { folderId } = useParams();
  const navigate = useNavigate();
  const { hasGlobal } = useAuth();
  const { alertMessage, confirmAction, promptText } = useDialog();

  const [allFolders, setAllFolders] = useState<FolderOut[]>([]);
  const [content, setContent] = useState<FolderContentOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [createKind, setCreateKind] = useState<CreateKind | null>(null);
  const [createForm, setCreateForm] = useState<CreateFormState>(() => initialCreateForm());
  const [creating, setCreating] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [selectionBox, setSelectionBox] = useState<{ startX: number; startY: number; x: number; y: number } | null>(null);
  const [bulkModalOpen, setBulkModalOpen] = useState(false);
  const [bulkActiveValue, setBulkActiveValue] = useState<"active" | "inactive">("active");
  const [bulkSaving, setBulkSaving] = useState(false);
  const gridRef = useRef<HTMLDivElement | null>(null);

  const reloadTree = useCallback(() => {
    foldersApi.tree().then(setAllFolders);
  }, []);

  const reloadContent = useCallback(() => {
    if (!folderId) {
      setContent(null);
      return;
    }
    setError(null);
    foldersApi
      .content(folderId)
      .then(setContent)
      .catch(() => setError("Нет доступа к этой папке или папка не найдена."));
  }, [folderId]);

  useEffect(() => {
    reloadTree();
  }, [reloadTree]);

  useEffect(() => {
    reloadContent();
  }, [reloadContent]);

  useEffect(() => {
    setSelectedIds([]);
    setSelectionBox(null);
    setBulkModalOpen(false);
  }, [folderId]);

  const rootFolders = useMemo(() => buildFolderTree(allFolders), [allFolders]);
  const selectableItems = useMemo<ContentSelectionItem[]>(() => {
    if (!content) return [];
    return [
      ...content.ingredients.map((ingredient) => ({
        kind: "ingredient" as const,
        id: ingredient.id,
        name: ingredient.name,
        isActive: ingredient.is_active,
      })),
      ...content.products.map((product) => ({
        kind: "product" as const,
        id: product.id,
        name: product.name,
        isActive: product.is_active,
      })),
      ...content.events.map((event) => ({
        kind: "event" as const,
        id: event.id,
        name: event.name,
        isActive: event.is_active,
      })),
    ];
  }, [content]);
  const selectedItems = useMemo(
    () => selectableItems.filter((item) => selectedIds.includes(contentItemKey(item))),
    [selectableItems, selectedIds],
  );
  const selectableIds = useMemo(() => selectableItems.map(contentItemKey), [selectableItems]);
  const allVisibleSelected = selectableIds.length > 0 && selectableIds.every((id) => selectedIds.includes(id));
  const currentTitle = content?.folder.name ?? "Корневые папки";
  const canCreateFolder = folderId ? !!content?.permissions.create : hasGlobal("admin.manage");
  const canCreateEntities = !!folderId && !!content?.permissions.edit;

  function openCreate(kind: CreateKind) {
    setCreateForm(initialCreateForm());
    setCreateKind(kind);
  }

  function closeCreate() {
    if (creating) return;
    setCreateKind(null);
  }

  function openItem(item: ContentSelectionItem) {
    if (item.kind === "ingredient") navigate(`/ingredients/${item.id}`);
    if (item.kind === "product") navigate(`/products/${item.id}`);
    if (item.kind === "event") navigate(`/events/${item.id}`);
  }

  function toggleSelect(item: ContentSelectionItem, additive: boolean) {
    const key = contentItemKey(item);
    setSelectedIds((current) => {
      if (!additive) return [key];
      return current.includes(key) ? current.filter((id) => id !== key) : [...current, key];
    });
  }

  function toggleSelectAllVisible() {
    setSelectedIds(allVisibleSelected ? [] : selectableIds);
  }

  function startSelection(event: ReactMouseEvent<HTMLDivElement>) {
    if (event.button !== 0 || (event.target as HTMLElement).closest(".content-card")) return;
    const grid = gridRef.current;
    if (!grid) return;

    const bounds = grid.getBoundingClientRect();
    const startX = event.clientX - bounds.left;
    const startY = event.clientY - bounds.top;
    setSelectedIds([]);
    setSelectionBox({ startX, startY, x: startX, y: startY });

    const selectInsideBox = (x: number, y: number) => {
      const left = Math.min(startX, x);
      const top = Math.min(startY, y);
      const right = Math.max(startX, x);
      const bottom = Math.max(startY, y);
      const ids = Array.from(grid.querySelectorAll<HTMLElement>("[data-select-id]"))
        .filter((card) => {
          const rect = card.getBoundingClientRect();
          const cardLeft = rect.left - bounds.left;
          const cardTop = rect.top - bounds.top;
          const cardRight = cardLeft + rect.width;
          const cardBottom = cardTop + rect.height;
          return cardLeft < right && cardRight > left && cardTop < bottom && cardBottom > top;
        })
        .map((card) => card.dataset.selectId)
        .filter((id): id is string => !!id);
      setSelectedIds(ids);
    };

    const onMouseMove = (moveEvent: MouseEvent) => {
      const x = moveEvent.clientX - bounds.left;
      const y = moveEvent.clientY - bounds.top;
      setSelectionBox({ startX, startY, x, y });
      selectInsideBox(x, y);
    };

    const onMouseUp = () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      setSelectionBox(null);
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }

  const selectionStyle: CSSProperties | undefined = selectionBox
    ? {
        left: Math.min(selectionBox.startX, selectionBox.x),
        top: Math.min(selectionBox.startY, selectionBox.y),
        width: Math.abs(selectionBox.x - selectionBox.startX),
        height: Math.abs(selectionBox.y - selectionBox.startY),
      }
    : undefined;

  async function handleMove(movedFolderId: string, newParentId: string | null) {
    await foldersApi.move(movedFolderId, newParentId);
    reloadTree();
    reloadContent();
  }

  async function handleCreateSubmit(event: FormEvent) {
    event.preventDefault();
    if (!createKind || !createForm.name.trim()) return;

    setCreating(true);
    try {
      if (createKind === "folder") {
        await foldersApi.create(createForm.name.trim(), folderId ?? null);
        reloadTree();
        reloadContent();
      }

      if (createKind === "ingredient" && folderId) {
        await ingredientsApi.create(folderId, {
          name: createForm.name.trim(),
          measure_type: createForm.measureType,
          description: createForm.description.trim() || null,
          allowed_container_weights_g: parseWeights(createForm.containerWeights),
          is_active: createForm.isActive,
        });
        reloadContent();
      }

      if (createKind === "product" && folderId) {
        const product = await productsApi.create(folderId, {
          name: createForm.name.trim(),
          base_quantity: createForm.baseQuantity,
        });
        navigate(`/products/${product.id}`);
      }

      if (createKind === "event" && folderId) {
        await eventsApi.create(folderId, {
          name: createForm.name.trim(),
          description: createForm.description.trim() || null,
          event_type: createForm.eventType,
          is_active: createForm.isActive,
        });
        reloadContent();
      }

      setCreateKind(null);
    } finally {
      setCreating(false);
    }
  }

  async function handleRenameFolder(folder: FolderOut) {
    const name = await promptText("Новое имя папки", folder.name);
    if (!name || name === folder.name) return;
    await foldersApi.rename(folder.id, name);
    reloadTree();
    reloadContent();
  }

  async function handleDeleteFolder(folder: FolderOut) {
    if (!(await confirmAction(`Удалить папку "${folder.name}"?`))) return;
    try {
      await foldersApi.remove(folder.id);
      reloadTree();
      reloadContent();
    } catch {
      alertMessage("Нельзя удалить папку: она не пустая или содержит используемые конфигурации.");
    }
  }

  async function updateItemActive(item: ContentSelectionItem, isActive: boolean) {
    if (item.kind === "ingredient") {
      await ingredientsApi.update(item.id, { is_active: isActive });
    }
    if (item.kind === "product") {
      await productsApi.update(item.id, { is_active: isActive });
    }
    if (item.kind === "event") {
      await eventsApi.update(item.id, { is_active: isActive });
    }
  }

  async function removeItem(item: ContentSelectionItem) {
    if (item.kind === "ingredient") {
      await ingredientsApi.remove(item.id);
    }
    if (item.kind === "product") {
      await productsApi.remove(item.id);
    }
    if (item.kind === "event") {
      await eventsApi.remove(item.id);
    }
  }

  async function applyBulkUpdate() {
    if (!selectedItems.length) return;
    setBulkSaving(true);
    try {
      const isActive = bulkActiveValue === "active";
      const results = await Promise.allSettled(selectedItems.map((item) => updateItemActive(item, isActive)));
      const failed = results.filter((result) => result.status === "rejected").length;
      reloadContent();
      setSelectedIds([]);
      setBulkModalOpen(false);
      alertMessage(failed ? `Изменено частично. Ошибок: ${failed}` : `Изменено объектов: ${selectedItems.length}`);
    } finally {
      setBulkSaving(false);
    }
  }

  async function deleteSelectedItems() {
    if (!selectedItems.length) return;
    if (!(await confirmAction(`Удалить выбранные объекты (${selectedItems.length})?`))) return;

    const results = await Promise.allSettled(selectedItems.map(removeItem));
    const failed = results.filter((result) => result.status === "rejected").length;
    reloadContent();
    setSelectedIds([]);
    alertMessage(failed ? `Удалено частично. Не удалось удалить: ${failed}` : `Удалено объектов: ${selectedItems.length}`);
  }

  return (
    <ConsoleShell
      title="Файлы"
      subtitle="Папки, ингредиенты, продукция и события в одной структуре с деревом слева."
    >
      <div className="file-manager-shell">
        <FolderTree folders={allFolders} currentFolderId={folderId ?? null} onMove={handleMove} />

        <section className="folder-content-panel">
          <div className="folder-content-toolbar">
            <div>
              <p className="eyebrow">{folderId ? "Текущая папка" : "Корень"}</p>
              <h2>{currentTitle}</h2>
              {content ? <Breadcrumbs items={content.breadcrumbs} /> : <p className="muted">Верхний уровень файловой структуры</p>}
            </div>

            <div className="create-action-grid">
              {canCreateFolder && (
                <button type="button" onClick={() => openCreate("folder")}>
                  <FolderPlus size={17} />
                  Папка
                </button>
              )}
              {canCreateEntities && (
                <>
                  <button type="button" onClick={() => openCreate("ingredient")}>
                    <Wheat size={17} />
                    Ингредиент
                  </button>
                  <button type="button" onClick={() => openCreate("product")}>
                    <PackagePlus size={17} />
                    Продукция
                  </button>
                  <button type="button" onClick={() => openCreate("event")}>
                    <BellRing size={17} />
                    Событие
                  </button>
                </>
              )}
            </div>
          </div>

          {!folderId && (
            <>
              {rootFolders.length === 0 ? (
                <div className="empty-folder">Корневых папок пока нет.</div>
              ) : (
                <div className="folder-content-grid">
                  {rootFolders.map((folder) => (
                    <div key={folder.id} className="content-card" onClick={() => navigate(`/files/${folder.id}`)}>
                      <div className="kind">
                        <FolderPlus size={14} />
                        Папка
                      </div>
                      <div className="name">{folder.name}</div>
                      <div className="meta">Открыть раздел</div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {error && <p className="error-text">{error}</p>}

          {content && (
            <>
              <div className="bulk-panel">
                <span>Выбрано: {selectedItems.length}</span>
                <button type="button" onClick={toggleSelectAllVisible} disabled={!selectableIds.length}>
                  {allVisibleSelected ? "Снять выделение" : "Выбрать все"}
                </button>
                {selectedItems.length > 0 && (
                  <>
                    <button type="button" onClick={() => setBulkModalOpen(true)} disabled={!content.permissions.edit}>
                      <Pencil size={16} />
                      Массовое изменение
                    </button>
                    <button
                      type="button"
                      className="danger"
                      onClick={() => void deleteSelectedItems()}
                      disabled={!content.permissions.edit}
                    >
                      <Trash2 size={16} />
                      Удалить
                    </button>
                    <button type="button" onClick={() => setSelectedIds([])}>
                      <XCircle size={16} />
                      Очистить
                    </button>
                  </>
                )}
                <span className="muted">Клик выбирает карточку, Ctrl+клик добавляет к выбору, рамкой можно выбрать несколько.</span>
              </div>

              <div className="file-grid-shell" ref={gridRef} onMouseDown={startSelection}>
                {selectionBox && <div className="selection-box" style={selectionStyle} />}
                <FolderContentGrid
                  subfolders={content.subfolders}
                  ingredients={content.ingredients}
                  products={content.products}
                  events={content.events}
                  selectedIds={selectedIds}
                  onOpenFolder={(id) => navigate(`/files/${id}`)}
                  onOpenItem={openItem}
                  onToggleSelect={toggleSelect}
                  onRenameFolder={handleRenameFolder}
                  onDeleteFolder={handleDeleteFolder}
                  canEdit={content.permissions.edit}
                />
              </div>
            </>
          )}
        </section>
      </div>

      {createKind && (
        <div className="modal-backdrop" role="presentation" onMouseDown={closeCreate}>
          <form className="modal-card" onSubmit={handleCreateSubmit} onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>{CREATE_TITLES[createKind].title}</h2>
                <p>{CREATE_TITLES[createKind].subtitle}</p>
              </div>
              <button type="button" className="icon-button" onClick={closeCreate} title="Закрыть">
                <Plus size={18} style={{ rotate: "45deg" }} />
              </button>
            </div>

            <div className="modal-body">
              <label className="modal-field">
                Название
                <input
                  autoFocus
                  value={createForm.name}
                  onChange={(event) => setCreateForm((prev) => ({ ...prev, name: event.target.value }))}
                  placeholder="Например: Мука пшеничная"
                  required
                />
              </label>

              {createKind === "ingredient" && (
                <div className="modal-grid">
                  <label className="modal-field">
                    Мера измерения
                    <select
                      value={createForm.measureType}
                      onChange={(event) =>
                        setCreateForm((prev) => ({ ...prev, measureType: event.target.value as MeasureType }))
                      }
                    >
                      {MEASURE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="modal-field">
                    Вес тары, г
                    <input
                      value={createForm.containerWeights}
                      onChange={(event) => setCreateForm((prev) => ({ ...prev, containerWeights: event.target.value }))}
                      placeholder="100, 250, 500"
                    />
                  </label>
                  <label className="modal-field span-2">
                    Описание
                    <textarea
                      value={createForm.description}
                      onChange={(event) => setCreateForm((prev) => ({ ...prev, description: event.target.value }))}
                      placeholder="Короткое описание для технологов"
                    />
                  </label>
                </div>
              )}

              {createKind === "product" && (
                <label className="modal-field">
                  Базовое количество, шт.
                  <input
                    type="number"
                    min={1}
                    value={createForm.baseQuantity}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, baseQuantity: Number(event.target.value) }))}
                  />
                </label>
              )}

              {createKind === "event" && (
                <div className="modal-grid">
                  <label className="modal-field">
                    Тип события
                    <select
                      value={createForm.eventType}
                      onChange={(event) =>
                        setCreateForm((prev) => ({ ...prev, eventType: event.target.value as EventType }))
                      }
                    >
                      {EVENT_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="modal-field span-2">
                    Описание
                    <textarea
                      value={createForm.description}
                      onChange={(event) => setCreateForm((prev) => ({ ...prev, description: event.target.value }))}
                      placeholder="Что должен подтвердить оператор"
                    />
                  </label>
                </div>
              )}

              {(createKind === "ingredient" || createKind === "event") && (
                <label className="checkbox-line">
                  <input
                    type="checkbox"
                    checked={createForm.isActive}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, isActive: event.target.checked }))}
                  />
                  Активно сразу после создания
                </label>
              )}
            </div>

            <div className="modal-footer">
              <button type="button" onClick={closeCreate}>
                Отмена
              </button>
              <button className="primary" type="submit" disabled={creating || !createForm.name.trim()}>
                {creating ? "Создание..." : "Создать"}
              </button>
            </div>
          </form>
        </div>
      )}

      {bulkModalOpen && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setBulkModalOpen(false)}>
          <div className="modal-card" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Массовое изменение</h2>
                <p>Выбрано объектов: {selectedItems.length}. Изменение применяется к ингредиентам, продукции и событиям.</p>
              </div>
              <button type="button" className="icon-button" onClick={() => setBulkModalOpen(false)} title="Закрыть">
                <Plus size={18} style={{ rotate: "45deg" }} />
              </button>
            </div>

            <div className="modal-body">
              <label className="modal-field">
                Активность
                <select
                  value={bulkActiveValue}
                  onChange={(event) => setBulkActiveValue(event.target.value as "active" | "inactive")}
                >
                  <option value="active">Сделать активными</option>
                  <option value="inactive">Отключить</option>
                </select>
              </label>
              <div className="system-role-note">
                Папки не входят в массовое изменение. Для них остаются отдельные действия переименования, удаления и перемещения.
              </div>
            </div>

            <div className="modal-footer">
              <button type="button" onClick={() => setBulkModalOpen(false)}>
                Отмена
              </button>
              <button className="primary" type="button" onClick={() => void applyBulkUpdate()} disabled={bulkSaving}>
                <CheckCircle2 size={17} />
                {bulkSaving ? "Применение..." : "Применить"}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConsoleShell>
  );
}
