import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Folder, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { rolesApi, tabsApi, foldersApi } from "../api/endpoints";
import type { AppTab, FolderOut, PermissionDef, Role, RolePermissionEntry } from "../api/types";
import { buildFolderTree, type FolderNode } from "../utils/folderTree";
import { useDialog } from "../components/DialogProvider";
import { ConsoleShell } from "../components/ConsoleShell";

type FolderPermissionKey = "view" | "create" | "edit";
type FolderPermissionState = Record<string, Record<FolderPermissionKey, boolean>>;

interface FolderPermissionRowsProps {
  node: FolderNode;
  depth: number;
  state: FolderPermissionState;
  selectedFolderId: string | null;
  onSelectFolder: (folderId: string) => void;
  onChange: (folderId: string, key: FolderPermissionKey, value: boolean) => void;
  inheritedFrom: (folderId: string, key: FolderPermissionKey) => FolderOut | null;
}

const FOLDER_PERMISSION_LABELS: Record<FolderPermissionKey, string> = {
  view: "Просмотр",
  create: "Создание",
  edit: "Редактирование",
};

function FolderPermissionRows({
  node,
  depth,
  state,
  selectedFolderId,
  onSelectFolder,
  onChange,
  inheritedFrom,
}: FolderPermissionRowsProps) {
  const ownState = state[node.id] ?? { view: false, create: false, edit: false };

  return (
    <>
      <div className={`folder-permission-row${selectedFolderId === node.id ? " active" : ""}`}>
        <button
          type="button"
          className="ghost permission-row-title"
          style={{ paddingLeft: 10 + depth * 16 }}
          onClick={() => onSelectFolder(node.id)}
        >
          <strong>{node.name}</strong>
          <small>Уровень {depth + 1}</small>
        </button>
        <div className="permission-switches">
          {(Object.keys(FOLDER_PERMISSION_LABELS) as FolderPermissionKey[]).map((key) => {
            const inherited = !ownState[key] ? inheritedFrom(node.id, key) : null;
            return (
              <label key={key}>
                <input
                  type="checkbox"
                  checked={!!ownState[key]}
                  onChange={(event) => onChange(node.id, key, event.target.checked)}
                />
                {FOLDER_PERMISSION_LABELS[key]}
                {inherited && <span className="inheritance-badge">от {inherited.name}</span>}
              </label>
            );
          })}
        </div>
      </div>
      {node.children.map((child) => (
        <FolderPermissionRows
          key={child.id}
          node={child}
          depth={depth + 1}
          state={state}
          selectedFolderId={selectedFolderId}
          onSelectFolder={onSelectFolder}
          onChange={onChange}
          inheritedFrom={inheritedFrom}
        />
      ))}
    </>
  );
}

function FolderInheritanceNode({
  node,
  depth,
  state,
  selectedFolderId,
  onSelectFolder,
  hasInheritedGrant,
}: {
  node: FolderNode;
  depth: number;
  state: FolderPermissionState;
  selectedFolderId: string | null;
  onSelectFolder: (folderId: string) => void;
  hasInheritedGrant: (folderId: string) => boolean;
}) {
  const own = state[node.id] ?? { view: false, create: false, edit: false };
  const hasOwnGrant = own.view || own.create || own.edit;
  const inherited = !hasOwnGrant && hasInheritedGrant(node.id);

  return (
    <>
      <button
        type="button"
        className={`inheritance-node${selectedFolderId === node.id ? " active" : ""}`}
        style={{ paddingLeft: 10 + depth * 16 }}
        onClick={() => onSelectFolder(node.id)}
      >
        <Folder size={16} />
        <span className="role-button-name">{node.name}</span>
        {hasOwnGrant && <span className="status-badge success">прямо</span>}
        {inherited && <span className="inheritance-badge">наследует</span>}
      </button>
      {node.children.map((child) => (
        <FolderInheritanceNode
          key={child.id}
          node={child}
          depth={depth + 1}
          state={state}
          selectedFolderId={selectedFolderId}
          onSelectFolder={onSelectFolder}
          hasInheritedGrant={hasInheritedGrant}
        />
      ))}
    </>
  );
}

export function RolesPermissions() {
  const { alertMessage } = useDialog();
  const [roles, setRoles] = useState<Role[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const [roleModalOpen, setRoleModalOpen] = useState(false);
  const [roleDraft, setRoleDraft] = useState({ name: "", description: "", orderVisibilityAhead: "" });
  const [roleSettingsDraft, setRoleSettingsDraft] = useState({ orderVisibilityAhead: "" });

  const [tabs, setTabs] = useState<AppTab[]>([]);
  const [folders, setFolders] = useState<FolderOut[]>([]);
  const [permDefs, setPermDefs] = useState<PermissionDef[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null);

  const [tabState, setTabState] = useState<Record<string, { view: boolean; edit: boolean }>>({});
  const [folderState, setFolderState] = useState<FolderPermissionState>({});
  const [globalState, setGlobalState] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [loadingRole, setLoadingRole] = useState(false);

  useEffect(() => {
    rolesApi.list().then(setRoles);
    tabsApi.list().then(setTabs);
    foldersApi.tree().then(setFolders);
    rolesApi.permissionDefs().then(setPermDefs);
  }, []);

  const selectedRole = roles.find((role) => role.id === selectedRoleId) ?? null;
  const folderTree = useMemo(() => buildFolderTree(folders), [folders]);
  const folderById = useMemo(() => new Map(folders.map((folder) => [folder.id, folder])), [folders]);
  const globalDefs = permDefs.filter((permission) => permission.scope_type === "global");

  const summary = useMemo(() => {
    const tabCount = Object.values(tabState).reduce((count, value) => count + Number(value.view) + Number(value.edit), 0);
    const folderCount = Object.values(folderState).reduce(
      (count, value) => count + Number(value.view) + Number(value.create) + Number(value.edit),
      0,
    );
    const globalCount = Object.values(globalState).filter(Boolean).length;
    return { tabCount, folderCount, globalCount };
  }, [folderState, globalState, tabState]);

  const selectRole = useCallback(async (roleId: string) => {
    setSelectedRoleId(roleId);
    const role = roles.find((item) => item.id === roleId);
    if (role) setRoleSettingsDraft({ orderVisibilityAhead: role.order_visibility_ahead?.toString() ?? "" });
    setLoadingRole(true);
    try {
      const permissions = await rolesApi.getPermissions(roleId);
      const nextTabState: Record<string, { view: boolean; edit: boolean }> = {};
      const nextFolderState: FolderPermissionState = {};
      const nextGlobalState: Record<string, boolean> = {};

      for (const permission of permissions) {
        if (permission.tab_id) {
          const entry = nextTabState[permission.tab_id] ?? { view: false, edit: false };
          if (permission.permission_code === "tab.view") entry.view = permission.granted;
          if (permission.permission_code === "tab.edit") entry.edit = permission.granted;
          nextTabState[permission.tab_id] = entry;
        } else if (permission.folder_id) {
          const entry = nextFolderState[permission.folder_id] ?? { view: false, create: false, edit: false };
          if (permission.permission_code === "folder.view") entry.view = permission.granted;
          if (permission.permission_code === "folder.create") entry.create = permission.granted;
          if (permission.permission_code === "folder.edit") entry.edit = permission.granted;
          nextFolderState[permission.folder_id] = entry;
        } else {
          nextGlobalState[permission.permission_code] = permission.granted;
        }
      }

      setTabState(nextTabState);
      setFolderState(nextFolderState);
      setGlobalState(nextGlobalState);
    } finally {
      setLoadingRole(false);
    }
  }, [roles]);

  useEffect(() => {
    if (!selectedRoleId && roles[0]) {
      void selectRole(roles[0].id);
    }
  }, [roles, selectedRoleId, selectRole]);

  async function createRole(event: FormEvent) {
    event.preventDefault();
    if (!roleDraft.name.trim()) return;
    const visibility = roleDraft.orderVisibilityAhead ? Number(roleDraft.orderVisibilityAhead) : null;
    const role = await rolesApi.create(roleDraft.name.trim(), roleDraft.description.trim() || undefined, visibility);
    setRoles((prev) => [...prev, role]);
    setRoleDraft({ name: "", description: "", orderVisibilityAhead: "" });
    setRoleModalOpen(false);
    setRoleSettingsDraft({ orderVisibilityAhead: role.order_visibility_ahead?.toString() ?? "" });
    await selectRole(role.id);
  }

  function toggleTab(tabId: string, key: "view" | "edit", value: boolean) {
    setTabState((prev) => ({ ...prev, [tabId]: { ...(prev[tabId] ?? { view: false, edit: false }), [key]: value } }));
  }

  function toggleFolder(folderId: string, key: FolderPermissionKey, value: boolean) {
    setFolderState((prev) => ({
      ...prev,
      [folderId]: { ...(prev[folderId] ?? { view: false, create: false, edit: false }), [key]: value },
    }));
  }

  function inheritedFrom(folderId: string, key: FolderPermissionKey) {
    let current = folderById.get(folderId);
    while (current?.parent_id) {
      const parent = folderById.get(current.parent_id);
      if (!parent) return null;
      if (folderState[parent.id]?.[key]) return parent;
      current = parent;
    }
    return null;
  }

  function hasInheritedGrant(folderId: string) {
    return !!inheritedFrom(folderId, "view") || !!inheritedFrom(folderId, "create") || !!inheritedFrom(folderId, "edit");
  }

  async function save() {
    if (!selectedRole) return;
    setSaving(true);
    try {
      const entries: RolePermissionEntry[] = [];
      for (const [tabId, state] of Object.entries(tabState)) {
        if (state.view) entries.push({ permission_code: "tab.view", tab_id: tabId, granted: true });
        if (state.edit) entries.push({ permission_code: "tab.edit", tab_id: tabId, granted: true });
      }
      for (const [folderId, state] of Object.entries(folderState)) {
        if (state.view) entries.push({ permission_code: "folder.view", folder_id: folderId, granted: true });
        if (state.create) entries.push({ permission_code: "folder.create", folder_id: folderId, granted: true });
        if (state.edit) entries.push({ permission_code: "folder.edit", folder_id: folderId, granted: true });
      }
      for (const [code, granted] of Object.entries(globalState)) {
        if (granted) entries.push({ permission_code: code, granted: true });
      }
      const visibility = roleSettingsDraft.orderVisibilityAhead ? Number(roleSettingsDraft.orderVisibilityAhead) : null;
      const updatedRole = await rolesApi.update(selectedRole.id, { order_visibility_ahead: visibility });
      setRoles((prev) => prev.map((role) => (role.id === selectedRole.id ? updatedRole : role)));
      await rolesApi.replacePermissions(selectedRole.id, entries);
      alertMessage("Права сохранены");
    } finally {
      setSaving(false);
    }
  }

  async function deleteSelectedRole() {
    if (!selectedRole || selectedRole.is_system) return;
    const confirmed = window.confirm(`Удалить роль «${selectedRole.name}»?`);
    if (!confirmed) return;
    await rolesApi.remove(selectedRole.id);
    setRoles((prev) => prev.filter((role) => role.id !== selectedRole.id));
    setSelectedRoleId(null);
    setRoleSettingsDraft({ orderVisibilityAhead: "" });
  }

  return (
    <ConsoleShell
      title="Роли и права"
      subtitle="Настройка вкладок, глобальных прав и наследуемого доступа по папкам."
      actions={
        <button type="button" className="primary" onClick={() => setRoleModalOpen(true)}>
          <Plus size={17} />
          Создать роль
        </button>
      }
    >
      <div className="permissions-layout">
        <aside className="permissions-panel">
          <div className="pane-heading">
            <div>
              <p className="eyebrow">Роли</p>
              <h2>Доступы</h2>
            </div>
          </div>

          <div className="role-list">
            {roles.map((role) => (
              <button
                key={role.id}
                type="button"
                className={role.id === selectedRoleId ? "active" : ""}
                onClick={() => void selectRole(role.id)}
              >
                <ShieldCheck size={16} />
                <span className="role-button-name">{role.name}</span>
                {role.is_system && <span className="status-badge">system</span>}
              </button>
            ))}
          </div>

          <div className="inheritance-tree">
            <div className="pane-heading">
              <div>
                <p className="eyebrow">Папки</p>
                <h2>Наследование</h2>
              </div>
            </div>
            {folderTree.length === 0 ? (
              <div className="empty-folder">Папок пока нет.</div>
            ) : (
              folderTree.map((node) => (
                <FolderInheritanceNode
                  key={node.id}
                  node={node}
                  depth={0}
                  state={folderState}
                  selectedFolderId={selectedFolderId}
                  onSelectFolder={setSelectedFolderId}
                  hasInheritedGrant={hasInheritedGrant}
                />
              ))
            )}
          </div>
        </aside>

        <section className="permissions-panel">
          {!selectedRole ? (
            <div className="empty-state">Выберите роль слева.</div>
          ) : (
            <>
              <div className="pane-heading">
                <div>
                  <p className="eyebrow">{loadingRole ? "Загрузка" : "Выбранная роль"}</p>
                  <h2>{selectedRole.name}</h2>
                </div>
                {!selectedRole.is_system && (
                  <div className="action-row">
                    <button className="danger" type="button" onClick={() => void deleteSelectedRole()}>
                      <Trash2 size={16} />
                      Удалить
                    </button>
                    <button className="primary" type="button" onClick={() => void save()} disabled={saving || loadingRole}>
                    {saving ? "Сохранение..." : "Сохранить права"}
                    </button>
                  </div>
                )}
              </div>

              {selectedRole.is_system ? (
                <div className="system-role-note">
                  Системная роль обходит проверки доступа. Для неё не требуется матрица прав: пользователь с этой ролью
                  видит и редактирует все разделы.
                </div>
              ) : (
                <>
                  <div className="permission-summary">
                    <article>
                      <strong>{summary.tabCount}</strong>
                      <span>прав по вкладкам</span>
                    </article>
                    <article>
                      <strong>{summary.folderCount}</strong>
                      <span>прямых прав на папки</span>
                    </article>
                    <article>
                      <strong>{summary.globalCount}</strong>
                      <span>глобальных прав</span>
                    </article>
                  </div>

                  <section className="permissions-section">
                    <div>
                      <p className="eyebrow">Очередь заявок</p>
                      <h2>Видимость позиций</h2>
                    </div>
                    <label className="editor-field">
                      Сколько позиций вперёд видит роль
                      <input
                        type="number"
                        min={1}
                        placeholder="Без ограничения"
                        value={roleSettingsDraft.orderVisibilityAhead}
                        onChange={(event) => setRoleSettingsDraft({ orderVisibilityAhead: event.target.value })}
                      />
                    </label>
                  </section>

                  <section className="permissions-section">
                    <div>
                      <p className="eyebrow">Вкладки справа</p>
                      <h2>Разделы интерфейса</h2>
                    </div>
                    <div className="permission-matrix">
                      {tabs.map((tab) => {
                        const state = tabState[tab.id] ?? { view: false, edit: false };
                        return (
                          <div key={tab.id} className="permission-row">
                            <div className="permission-row-title">
                              <strong>{tab.label}</strong>
                              <small>{tab.key}</small>
                            </div>
                            <div className="permission-switches">
                              <label>
                                <input
                                  type="checkbox"
                                  checked={state.view}
                                  onChange={(event) => toggleTab(tab.id, "view", event.target.checked)}
                                />
                                Просмотр
                              </label>
                              <label>
                                <input
                                  type="checkbox"
                                  checked={state.edit}
                                  onChange={(event) => toggleTab(tab.id, "edit", event.target.checked)}
                                />
                                Изменение
                              </label>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </section>

                  <section className="permissions-section">
                    <div>
                      <p className="eyebrow">Дерево слева</p>
                      <h2>Права на папки</h2>
                    </div>
                    <div className="permission-matrix">
                      {folderTree.map((node) => (
                        <FolderPermissionRows
                          key={node.id}
                          node={node}
                          depth={0}
                          state={folderState}
                          selectedFolderId={selectedFolderId}
                          onSelectFolder={setSelectedFolderId}
                          onChange={toggleFolder}
                          inheritedFrom={inheritedFrom}
                        />
                      ))}
                    </div>
                  </section>

                  <section className="permissions-section">
                    <div>
                      <p className="eyebrow">Глобально</p>
                      <h2>Системные действия</h2>
                    </div>
                    <div className="permission-matrix">
                      {globalDefs.map((permission) => (
                        <div key={permission.code} className="global-permission-row">
                          <div className="permission-row-title">
                            <strong>{permission.label}</strong>
                            <small>{permission.code}</small>
                          </div>
                          <div className="permission-switches">
                            <label>
                              <input
                                type="checkbox"
                                checked={!!globalState[permission.code]}
                                onChange={(event) =>
                                  setGlobalState((prev) => ({ ...prev, [permission.code]: event.target.checked }))
                                }
                              />
                              Разрешить
                            </label>
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                </>
              )}
            </>
          )}
        </section>
      </div>

      {roleModalOpen && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setRoleModalOpen(false)}>
          <form className="modal-card" onSubmit={createRole} onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Новая роль</h2>
                <p>Создайте роль, а затем настройте вкладки, папки и глобальные права.</p>
              </div>
              <button type="button" className="icon-button" onClick={() => setRoleModalOpen(false)} title="Закрыть">
                <Plus size={18} style={{ rotate: "45deg" }} />
              </button>
            </div>
            <div className="modal-body">
              <label className="modal-field">
                Название роли
                <input
                  autoFocus
                  value={roleDraft.name}
                  onChange={(event) => setRoleDraft((prev) => ({ ...prev, name: event.target.value }))}
                  placeholder="Например: Технолог"
                  required
                />
              </label>
              <label className="modal-field">
                Описание
                <textarea
                  value={roleDraft.description}
                  onChange={(event) => setRoleDraft((prev) => ({ ...prev, description: event.target.value }))}
                  placeholder="Кому назначается роль и зачем"
                />
              </label>
              <label className="modal-field">
                Видимость заявки, позиций вперёд
                <input
                  type="number"
                  min={1}
                  value={roleDraft.orderVisibilityAhead}
                  onChange={(event) =>
                    setRoleDraft((prev) => ({ ...prev, orderVisibilityAhead: event.target.value }))
                  }
                  placeholder="Без ограничения"
                />
              </label>
            </div>
            <div className="modal-footer">
              <button type="button" onClick={() => setRoleModalOpen(false)}>
                Отмена
              </button>
              <button className="primary" type="submit" disabled={!roleDraft.name.trim()}>
                Создать
              </button>
            </div>
          </form>
        </div>
      )}
    </ConsoleShell>
  );
}
