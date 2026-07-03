import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { rolesApi, tabsApi, foldersApi } from "../api/endpoints";
import type { AppTab, FolderOut, PermissionDef, Role, RolePermissionEntry } from "../api/types";
import { buildFolderTree, type FolderNode } from "../utils/folderTree";
import { useDialog } from "../components/DialogProvider";

function FolderCheckRow({
  node,
  depth,
  state,
  onChange,
}: {
  node: FolderNode;
  depth: number;
  state: Record<string, { view: boolean; create: boolean; edit: boolean }>;
  onChange: (folderId: string, key: "view" | "create" | "edit", value: boolean) => void;
}) {
  const s = state[node.id] ?? { view: false, create: false, edit: false };
  return (
    <>
      <div style={{ paddingLeft: depth * 16, display: "flex", gap: 12, alignItems: "center", padding: "3px 0" }}>
        <span style={{ minWidth: 200 }}>{node.name}</span>
        <label>
          <input type="checkbox" checked={s.view} onChange={(e) => onChange(node.id, "view", e.target.checked)} /> view
        </label>
        <label>
          <input type="checkbox" checked={s.create} onChange={(e) => onChange(node.id, "create", e.target.checked)} /> create
        </label>
        <label>
          <input type="checkbox" checked={s.edit} onChange={(e) => onChange(node.id, "edit", e.target.checked)} /> edit
        </label>
      </div>
      {node.children.map((c) => (
        <FolderCheckRow key={c.id} node={c} depth={depth + 1} state={state} onChange={onChange} />
      ))}
    </>
  );
}

export function RolesPermissions() {
  const { alertMessage } = useDialog();
  const [roles, setRoles] = useState<Role[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const [newRoleName, setNewRoleName] = useState("");

  const [tabs, setTabs] = useState<AppTab[]>([]);
  const [folders, setFolders] = useState<FolderOut[]>([]);
  const [permDefs, setPermDefs] = useState<PermissionDef[]>([]);

  const [tabState, setTabState] = useState<Record<string, { view: boolean; edit: boolean }>>({});
  const [folderState, setFolderState] = useState<Record<string, { view: boolean; create: boolean; edit: boolean }>>({});
  const [globalState, setGlobalState] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    rolesApi.list().then(setRoles);
    tabsApi.list().then(setTabs);
    foldersApi.tree().then(setFolders);
    rolesApi.permissionDefs().then(setPermDefs);
  }, []);

  const selectedRole = roles.find((r) => r.id === selectedRoleId) ?? null;
  const folderTree = useMemo(() => buildFolderTree(folders), [folders]);
  const globalDefs = permDefs.filter((p) => p.scope_type === "global");

  async function selectRole(roleId: string) {
    setSelectedRoleId(roleId);
    const perms = await rolesApi.getPermissions(roleId);
    const nextTabState: Record<string, { view: boolean; edit: boolean }> = {};
    const nextFolderState: Record<string, { view: boolean; create: boolean; edit: boolean }> = {};
    const nextGlobalState: Record<string, boolean> = {};
    for (const p of perms) {
      if (p.tab_id) {
        const entry = nextTabState[p.tab_id] ?? { view: false, edit: false };
        if (p.permission_code === "tab.view") entry.view = p.granted;
        if (p.permission_code === "tab.edit") entry.edit = p.granted;
        nextTabState[p.tab_id] = entry;
      } else if (p.folder_id) {
        const entry = nextFolderState[p.folder_id] ?? { view: false, create: false, edit: false };
        if (p.permission_code === "folder.view") entry.view = p.granted;
        if (p.permission_code === "folder.create") entry.create = p.granted;
        if (p.permission_code === "folder.edit") entry.edit = p.granted;
        nextFolderState[p.folder_id] = entry;
      } else {
        nextGlobalState[p.permission_code] = p.granted;
      }
    }
    setTabState(nextTabState);
    setFolderState(nextFolderState);
    setGlobalState(nextGlobalState);
  }

  async function createRole() {
    if (!newRoleName.trim()) return;
    const role = await rolesApi.create(newRoleName.trim());
    setRoles((prev) => [...prev, role]);
    setNewRoleName("");
    await selectRole(role.id);
  }

  function toggleTab(tabId: string, key: "view" | "edit", value: boolean) {
    setTabState((prev) => ({ ...prev, [tabId]: { ...(prev[tabId] ?? { view: false, edit: false }), [key]: value } }));
  }

  function toggleFolder(folderId: string, key: "view" | "create" | "edit", value: boolean) {
    setFolderState((prev) => ({
      ...prev,
      [folderId]: { ...(prev[folderId] ?? { view: false, create: false, edit: false }), [key]: value },
    }));
  }

  async function save() {
    if (!selectedRole) return;
    setSaving(true);
    try {
      const entries: RolePermissionEntry[] = [];
      for (const [tabId, s] of Object.entries(tabState)) {
        if (s.view) entries.push({ permission_code: "tab.view", tab_id: tabId, granted: true });
        if (s.edit) entries.push({ permission_code: "tab.edit", tab_id: tabId, granted: true });
      }
      for (const [folderId, s] of Object.entries(folderState)) {
        if (s.view) entries.push({ permission_code: "folder.view", folder_id: folderId, granted: true });
        if (s.create) entries.push({ permission_code: "folder.create", folder_id: folderId, granted: true });
        if (s.edit) entries.push({ permission_code: "folder.edit", folder_id: folderId, granted: true });
      }
      for (const [code, granted] of Object.entries(globalState)) {
        if (granted) entries.push({ permission_code: code, granted: true });
      }
      await rolesApi.replacePermissions(selectedRole.id, entries);
      alertMessage("Права сохранены");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="page-topbar">
        <Link to="/">← Главная</Link>
        <h2 style={{ margin: 0 }}>Роли и права</h2>
      </div>
      <div style={{ display: "flex", gap: 24, padding: 16 }}>
        <div style={{ width: 220 }}>
          <h3>Роли</h3>
          {roles.map((r) => (
            <div
              key={r.id}
              onClick={() => selectRole(r.id)}
              style={{
                padding: "6px 8px",
                cursor: "pointer",
                background: r.id === selectedRoleId ? "#e3efe8" : "transparent",
                borderRadius: 4,
              }}
            >
              {r.name} {r.is_system && "🔒"}
            </div>
          ))}
          <div style={{ marginTop: 12, display: "flex", gap: 6 }}>
            <input placeholder="Новая роль" value={newRoleName} onChange={(e) => setNewRoleName(e.target.value)} />
            <button onClick={createRole}>+</button>
          </div>
        </div>

        {selectedRole && (
          <div style={{ flex: 1 }}>
            <h3>
              {selectedRole.name} {selectedRole.is_system && "(системная роль, обходит все проверки)"}
            </h3>

            {!selectedRole.is_system && (
              <>
                <h4>Вкладки</h4>
                {tabs.map((t) => {
                  const s = tabState[t.id] ?? { view: false, edit: false };
                  return (
                    <div key={t.id} style={{ display: "flex", gap: 12, alignItems: "center", padding: "3px 0" }}>
                      <span style={{ minWidth: 200 }}>{t.label}</span>
                      <label>
                        <input type="checkbox" checked={s.view} onChange={(e) => toggleTab(t.id, "view", e.target.checked)} /> view
                      </label>
                      <label>
                        <input type="checkbox" checked={s.edit} onChange={(e) => toggleTab(t.id, "edit", e.target.checked)} /> edit
                      </label>
                    </div>
                  );
                })}

                <h4>Папки</h4>
                {folderTree.map((n) => (
                  <FolderCheckRow key={n.id} node={n} depth={0} state={folderState} onChange={toggleFolder} />
                ))}

                <h4>Глобальные права</h4>
                {globalDefs.map((d) => (
                  <div key={d.code} style={{ display: "flex", gap: 12, alignItems: "center", padding: "3px 0" }}>
                    <label>
                      <input
                        type="checkbox"
                        checked={!!globalState[d.code]}
                        onChange={(e) => setGlobalState((prev) => ({ ...prev, [d.code]: e.target.checked }))}
                      />{" "}
                      {d.label}
                    </label>
                  </div>
                ))}

                <button className="primary" style={{ marginTop: 16 }} onClick={save} disabled={saving}>
                  {saving ? "Сохранение..." : "Сохранить"}
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
