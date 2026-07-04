import { BellRing, Folder, Package, Pencil, Trash2, Wheat } from "lucide-react";
import type { EventBrief, FolderOut, IngredientBrief, ProductBrief } from "../api/types";
import { contentItemKey, type ContentSelectionItem } from "../utils/contentSelection";

interface FolderContentGridProps {
  subfolders: FolderOut[];
  ingredients: IngredientBrief[];
  products: ProductBrief[];
  events: EventBrief[];
  selectedIds: string[];
  onOpenFolder: (folderId: string) => void;
  onOpenItem: (item: ContentSelectionItem) => void;
  onToggleSelect: (item: ContentSelectionItem, additive: boolean) => void;
  onRenameFolder: (folder: FolderOut) => void;
  onDeleteFolder: (folder: FolderOut) => void;
  canEdit: boolean;
}

export function FolderContentGrid({
  subfolders,
  ingredients,
  products,
  events,
  selectedIds,
  onOpenFolder,
  onOpenItem,
  onToggleSelect,
  onRenameFolder,
  onDeleteFolder,
  canEdit,
}: FolderContentGridProps) {
  if (subfolders.length === 0 && ingredients.length === 0 && products.length === 0 && events.length === 0) {
    return <div className="empty-folder">Папка пустая. Создайте папку, ингредиент, продукцию или событие.</div>;
  }

  function renderSelectableCard(item: ContentSelectionItem, meta: string, icon: "ingredient" | "product" | "event") {
    const key = contentItemKey(item);
    const selected = selectedIds.includes(key);
    const Icon = icon === "ingredient" ? Wheat : icon === "product" ? Package : BellRing;
    const kindLabel = icon === "ingredient" ? "Ингредиент" : icon === "product" ? "Продукция" : "Событие";

    return (
      <div
        key={key}
        data-select-id={key}
        className={`content-card selectable${selected ? " selected" : ""}${item.isActive ? "" : " inactive"}`}
        onClick={(event) => onToggleSelect(item, event.ctrlKey || event.metaKey || event.shiftKey)}
        onDoubleClick={() => onOpenItem(item)}
      >
        <label className="selection-check" onClick={(event) => event.stopPropagation()}>
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onToggleSelect(item, true)}
            aria-label={`Выбрать ${item.name}`}
          />
        </label>
        <div className="kind">
          <Icon size={14} />
          {kindLabel}
        </div>
        <div className="name">{item.name}</div>
        <div className="meta">{meta}</div>
        <button
          type="button"
          className="open-card-button"
          onClick={(event) => {
            event.stopPropagation();
            onOpenItem(item);
          }}
        >
          Открыть
        </button>
      </div>
    );
  }

  return (
    <div className="folder-content-grid">
      {subfolders.map((folder) => (
        <div
          key={folder.id}
          className="content-card"
          draggable
          onDragStart={(event) => event.dataTransfer.setData("text/folder-id", folder.id)}
          onClick={() => onOpenFolder(folder.id)}
        >
          <div className="kind">
            <Folder size={14} />
            Папка
          </div>
          <div className="name">{folder.name}</div>
          <div className="meta">Открыть структуру</div>
          {canEdit && (
            <div className="card-actions" onClick={(event) => event.stopPropagation()}>
              <button type="button" onClick={() => onRenameFolder(folder)} title="Переименовать">
                <Pencil size={15} />
              </button>
              <button type="button" className="danger" onClick={() => onDeleteFolder(folder)} title="Удалить">
                <Trash2 size={15} />
              </button>
            </div>
          )}
        </div>
      ))}

      {ingredients.map((ingredient) =>
        renderSelectableCard(
          { kind: "ingredient", id: ingredient.id, name: ingredient.name, isActive: ingredient.is_active },
          ingredient.is_active ? "Активен" : "Отключён",
          "ingredient",
        ),
      )}

      {products.map((product) =>
        renderSelectableCard(
          { kind: "product", id: product.id, name: product.name, isActive: product.is_active },
          `База: ${product.base_quantity} шт.`,
          "product",
        ),
      )}

      {events.map((event) =>
        renderSelectableCard(
          { kind: "event", id: event.id, name: event.name, isActive: event.is_active },
          event.is_active ? "Активно" : "Отключено",
          "event",
        ),
      )}
    </div>
  );
}
