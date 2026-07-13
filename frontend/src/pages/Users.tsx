import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { rolesApi, usersApi } from "../api/endpoints";
import type { Role, UserListOut } from "../api/types";

export function Users() {
  const [users, setUsers] = useState<UserListOut[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [selected, setSelected] = useState<UserListOut | null>(null);
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);

  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newFullName, setNewFullName] = useState("");

  function reloadUsers() {
    usersApi.list().then(setUsers);
  }

  useEffect(() => {
    reloadUsers();
    rolesApi.list().then(setRoles);
  }, []);

  function selectUser(u: UserListOut) {
    setSelected(u);
    setSelectedRoleIds(roles.filter((r) => u.role_names.includes(r.name)).map((r) => r.id));
  }

  async function createUser() {
    if (!newEmail || !newPassword || !newFullName) return;
    await usersApi.create({ email: newEmail, password: newPassword, full_name: newFullName });
    setNewEmail("");
    setNewPassword("");
    setNewFullName("");
    reloadUsers();
  }

  async function saveRoles() {
    if (!selected) return;
    await usersApi.setRoles(selected.id, selectedRoleIds);
    reloadUsers();
    setSelected(null);
  }

  async function toggleActive(u: UserListOut) {
    await usersApi.update(u.id, { is_active: !u.is_active });
    reloadUsers();
  }

  async function toggleVoiceAssistant(u: UserListOut) {
    await usersApi.update(u.id, { voice_assistant_enabled: !u.voice_assistant_enabled });
    reloadUsers();
  }

  return (
    <div>
      <div className="page-topbar">
        <Link to="/">← Главная</Link>
        <h2 style={{ margin: 0 }}>Пользователи</h2>
      </div>
      <div style={{ padding: 16 }}>
        <table className="order-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Имя</th>
              <th>Роли</th>
              <th>Статус</th>
              <th>Голос. помощник</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td>
                <td>{u.full_name}</td>
                <td>{u.role_names.join(", ") || "—"}</td>
                <td>{u.is_active ? "активен" : "заблокирован"}</td>
                <td>{u.voice_assistant_enabled ? "включен" : "выключен"}</td>
                <td style={{ display: "flex", gap: 6 }}>
                  <button onClick={() => selectUser(u)}>Роли</button>
                  <button onClick={() => toggleActive(u)}>{u.is_active ? "Заблокировать" : "Активировать"}</button>
                  <button onClick={() => toggleVoiceAssistant(u)}>
                    {u.voice_assistant_enabled ? "Выключить голос" : "Включить голос"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <h3 style={{ marginTop: 24 }}>Новый пользователь</h3>
        <div style={{ display: "flex", gap: 8 }}>
          <input placeholder="Email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} />
          <input placeholder="Имя" value={newFullName} onChange={(e) => setNewFullName(e.target.value)} />
          <input
            placeholder="Пароль"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />
          <button className="primary" onClick={createUser}>
            Создать
          </button>
        </div>

        {selected && (
          <div style={{ marginTop: 24, padding: 16, border: "1px solid var(--border)", borderRadius: 8 }}>
            <h4>Роли пользователя {selected.email}</h4>
            {roles.map((r) => (
              <label key={r.id} style={{ display: "block" }}>
                <input
                  type="checkbox"
                  checked={selectedRoleIds.includes(r.id)}
                  onChange={(e) =>
                    setSelectedRoleIds((prev) =>
                      e.target.checked ? [...prev, r.id] : prev.filter((id) => id !== r.id),
                    )
                  }
                />{" "}
                {r.name}
              </label>
            ))}
            <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
              <button className="primary" onClick={saveRoles}>
                Сохранить
              </button>
              <button onClick={() => setSelected(null)}>Отмена</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
