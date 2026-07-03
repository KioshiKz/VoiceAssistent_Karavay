import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { eventsApi, foldersApi, ingredientsApi, productsApi } from "../api/endpoints";
import type { FolderContentOut, FolderOut } from "../api/types";
import { FolderTree } from "../components/FolderTree";
import { Breadcrumbs } from "../components/Breadcrumbs";
import { FolderContentGrid } from "../components/FolderContentGrid";
import { useAuth } from "../auth/AuthContext";
import { useDialog } from "../components/DialogProvider";
import { buildFolderTree } from "../utils/folderTree";

export function FileManager() {
  const { folderId } = useParams();
  const navigate = useNavigate();
  const { hasGlobal } = useAuth();
  const { alertMessage, confirmAction, promptText } = useDialog();

  const [allFolders, setAllFolders] = useState<FolderOut[]>([]);
  const [content, setContent] = useState<FolderContentOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [newFolderName, setNewFolderName] = useState("");
  const [newIngredientName, setNewIngredientName] = useState("");
  const [newProductName, setNewProductName] = useState("");
  const [newEventName, setNewEventName] = useState("");
  const [showCreateForm, setShowCreateForm] = useState<"folder" | "ingredient" | "product" | "event" | null>(null);

  const reloadTree = useCallback(() => {
    foldersApi.tree().then(setAllFolders);
  }, []);

  const reloadContent = useCallback(() => {
    if (!folderId) {
      setContent(null);
      return;
    }
    setError(null);
    foldersApi.content(folderId).catch(() => setError("Нет доступа к этой папке или папка не найдена.")).then((c) => {
      if (c) setContent(c);
    });
  }, [folderId]);

  useEffect(() => {
    reloadTree();
  }, [reloadTree]);

  useEffect(() => {
    reloadContent();
  }, [reloadContent]);

  async function handleMove(movedFolderId: string, newParentId: string | null) {
    await foldersApi.move(movedFolderId, newParentId);
    reloadTree();
    reloadContent();
  }

  async function handleCreateFolder() {
    if (!newFolderName.trim()) return;
    await foldersApi.create(newFolderName.trim(), folderId ?? null);
    setNewFolderName("");
    setShowCreateForm(null);
    reloadTree();
    reloadContent();
  }

  async function handleCreateIngredient() {
    if (!newIngredientName.trim() || !folderId) return;
    await ingredientsApi.create(folderId, {
      name: newIngredientName.trim(),
      measure_type: "weight",
      description: null,
      allowed_container_weights_g: null,
      is_active: true,
    });
    setNewIngredientName("");
    setShowCreateForm(null);
    reloadContent();
  }

  async function handleCreateProduct() {
    if (!newProductName.trim() || !folderId) return;
    const p = await productsApi.create(folderId, { name: newProductName.trim(), base_quantity: 100 });
    setNewProductName("");
    setShowCreateForm(null);
    navigate(`/products/${p.id}`);
  }

  async function handleCreateEvent() {
    if (!newEventName.trim() || !folderId) return;
    await eventsApi.create(folderId, {
      name: newEventName.trim(),
      description: null,
      event_type: "timer",
      is_active: true,
    });
    setNewEventName("");
    setShowCreateForm(null);
    reloadContent();
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
      alertMessage("Нельзя удалить: папка не пуста или в ней есть используемые конфиги.");
    }
  }

  // "Effective" roots: real root folders (parent_id null) plus folders whose
  // parent isn't in the visible set (e.g. a restricted role can see a subfolder
  // without permission on its ancestor) — same logic buildFolderTree uses for the tree.
  const rootFolders = useMemo(() => buildFolderTree(allFolders), [allFolders]);

  return (
    <div>
      <div className="page-topbar">
        <Link to="/">← Главная</Link>
        {content ? <Breadcrumbs items={content.breadcrumbs} /> : <span>Файлы</span>}
      </div>
      <div className="file-manager">
        <FolderTree folders={allFolders} currentFolderId={folderId ?? null} onMove={handleMove} />
        <div className="folder-content">
          {!folderId && (
            <div>
              <h3>Корневые папки</h3>
              {rootFolders.length === 0 && <p style={{ color: "#888" }}>Папок пока нет.</p>}
              <div className="folder-content-grid">
                {rootFolders.map((f) => (
                  <div key={f.id} className="content-card" onDoubleClick={() => navigate(`/files/${f.id}`)}>
                    <div className="kind">Папка</div>
                    <div className="name">📁 {f.name}</div>
                  </div>
                ))}
              </div>
              {hasGlobal("admin.manage") && (
                <div style={{ marginTop: 16 }}>
                  <input
                    placeholder="Название корневой папки"
                    value={newFolderName}
                    onChange={(e) => setNewFolderName(e.target.value)}
                  />
                  <button className="primary" onClick={handleCreateFolder} style={{ marginLeft: 8 }}>
                    Создать корневую папку
                  </button>
                </div>
              )}
            </div>
          )}

          {error && <p className="error-text">{error}</p>}

          {content && (
            <>
              <div className="folder-content-toolbar">
                {content.permissions.create && (
                  <button onClick={() => setShowCreateForm("folder")}>+ Папка</button>
                )}
                {content.permissions.edit && (
                  <>
                    <button onClick={() => setShowCreateForm("ingredient")}>+ Ингредиент</button>
                    <button onClick={() => setShowCreateForm("product")}>+ Продукция</button>
                    <button onClick={() => setShowCreateForm("event")}>+ Событие</button>
                  </>
                )}
              </div>

              {showCreateForm === "folder" && (
                <div style={{ marginBottom: 12 }}>
                  <input
                    placeholder="Название папки"
                    value={newFolderName}
                    onChange={(e) => setNewFolderName(e.target.value)}
                  />
                  <button className="primary" onClick={handleCreateFolder} style={{ marginLeft: 8 }}>
                    Создать
                  </button>
                </div>
              )}
              {showCreateForm === "ingredient" && (
                <div style={{ marginBottom: 12 }}>
                  <input
                    placeholder="Название ингредиента"
                    value={newIngredientName}
                    onChange={(e) => setNewIngredientName(e.target.value)}
                  />
                  <button className="primary" onClick={handleCreateIngredient} style={{ marginLeft: 8 }}>
                    Создать
                  </button>
                </div>
              )}
              {showCreateForm === "product" && (
                <div style={{ marginBottom: 12 }}>
                  <input
                    placeholder="Название продукции"
                    value={newProductName}
                    onChange={(e) => setNewProductName(e.target.value)}
                  />
                  <button className="primary" onClick={handleCreateProduct} style={{ marginLeft: 8 }}>
                    Создать
                  </button>
                </div>
              )}
              {showCreateForm === "event" && (
                <div style={{ marginBottom: 12 }}>
                  <input
                    placeholder="Название события"
                    value={newEventName}
                    onChange={(e) => setNewEventName(e.target.value)}
                  />
                  <button className="primary" onClick={handleCreateEvent} style={{ marginLeft: 8 }}>
                    Создать
                  </button>
                </div>
              )}

              <FolderContentGrid
                subfolders={content.subfolders}
                ingredients={content.ingredients}
                products={content.products}
                events={content.events}
                onOpenFolder={(id) => navigate(`/files/${id}`)}
                onRenameFolder={handleRenameFolder}
                onDeleteFolder={handleDeleteFolder}
                canEdit={content.permissions.edit}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
