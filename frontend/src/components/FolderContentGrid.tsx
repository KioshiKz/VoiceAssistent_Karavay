import { useNavigate } from "react-router-dom";
import type { EventBrief, FolderOut, IngredientBrief, ProductBrief } from "../api/types";

interface FolderContentGridProps {
  subfolders: FolderOut[];
  ingredients: IngredientBrief[];
  products: ProductBrief[];
  events: EventBrief[];
  onOpenFolder: (folderId: string) => void;
  onRenameFolder: (folder: FolderOut) => void;
  onDeleteFolder: (folder: FolderOut) => void;
  canEdit: boolean;
}

export function FolderContentGrid({
  subfolders,
  ingredients,
  products,
  events,
  onOpenFolder,
  onRenameFolder,
  onDeleteFolder,
  canEdit,
}: FolderContentGridProps) {
  const navigate = useNavigate();

  if (subfolders.length === 0 && ingredients.length === 0 && products.length === 0 && events.length === 0) {
    return <p style={{ color: "#888" }}>Папка пуста.</p>;
  }

  return (
    <div className="folder-content-grid">
      {subfolders.map((f) => (
        <div
          key={f.id}
          className="content-card"
          draggable
          onDragStart={(e) => e.dataTransfer.setData("text/folder-id", f.id)}
          onDoubleClick={() => onOpenFolder(f.id)}
        >
          <div className="kind">Папка</div>
          <div className="name">📁 {f.name}</div>
          {canEdit && (
            <div style={{ marginTop: 8, display: "flex", gap: 6 }}>
              <button onClick={() => onRenameFolder(f)}>✎</button>
              <button onClick={() => onDeleteFolder(f)}>✕</button>
            </div>
          )}
        </div>
      ))}

      {ingredients.map((i) => (
        <div
          key={i.id}
          className={`content-card${i.is_active ? "" : " inactive"}`}
          onDoubleClick={() => navigate(`/ingredients/${i.id}`)}
        >
          <div className="kind">Ингредиент</div>
          <div className="name">🧂 {i.name}</div>
        </div>
      ))}

      {products.map((p) => (
        <div
          key={p.id}
          className={`content-card${p.is_active ? "" : " inactive"}`}
          onDoubleClick={() => navigate(`/products/${p.id}`)}
        >
          <div className="kind">Продукция</div>
          <div className="name">🍞 {p.name}</div>
        </div>
      ))}

      {events.map((e) => (
        <div
          key={e.id}
          className={`content-card${e.is_active ? "" : " inactive"}`}
          onDoubleClick={() => navigate(`/events/${e.id}`)}
        >
          <div className="kind">Событие</div>
          <div className="name">⏱ {e.name}</div>
        </div>
      ))}
    </div>
  );
}
