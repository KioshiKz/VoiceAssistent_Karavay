import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Mic, MicOff, Plus, ShieldCheck, UserCheck, UserX, X } from "lucide-react";
import { rolesApi, usersApi } from "../api/endpoints";
import type { Role, UserListOut } from "../api/types";
import { ConsoleShell } from "../components/ConsoleShell";
import { useDialog } from "../components/DialogProvider";

const EMPTY_USER_DRAFT = { email: "", fullName: "", password: "" };

export function Users() {
  const { alertMessage } = useDialog();
  const [users, setUsers] = useState<UserListOut[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [selected, setSelected] = useState<UserListOut | null>(null);
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [userDraft, setUserDraft] = useState(EMPTY_USER_DRAFT);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [savingRoles, setSavingRoles] = useState(false);
  const [busyUserId, setBusyUserId] = useState<string | null>(null);

  const reloadUsers = useCallback(async () => {
    const nextUsers = await usersApi.list();
    setUsers(nextUsers);
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadError(null);

    Promise.all([usersApi.list(), rolesApi.list()])
      .then(([nextUsers, nextRoles]) => {
        if (!active) return;
        setUsers(nextUsers);
        setRoles(nextRoles);
      })
      .catch(() => {
        if (active) setLoadError("Не удалось загрузить пользователей.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  function openCreateDialog() {
    setUserDraft(EMPTY_USER_DRAFT);
    setCreateError(null);
    setCreateOpen(true);
  }

  function selectUser(user: UserListOut) {
    setSelected(user);
    setSelectedRoleIds(roles.filter((role) => user.role_names.includes(role.name)).map((role) => role.id));
  }

  async function createUser(event: FormEvent) {
    event.preventDefault();
    const email = userDraft.email.trim();
    const fullName = userDraft.fullName.trim();
    if (!email || !fullName || !userDraft.password) return;

    setCreating(true);
    setCreateError(null);
    try {
      await usersApi.create({ email, password: userDraft.password, full_name: fullName });
      await reloadUsers();
      setCreateOpen(false);
      setUserDraft(EMPTY_USER_DRAFT);
      alertMessage("Пользователь создан");
    } catch {
      setCreateError("Не удалось создать пользователя. Проверьте Email или возьмите другой.");
    } finally {
      setCreating(false);
    }
  }

  async function saveRoles() {
    if (!selected) return;
    setSavingRoles(true);
    try {
      const updated = await usersApi.setRoles(selected.id, selectedRoleIds);
      setUsers((current) => current.map((user) => (user.id === updated.id ? updated : user)));
      setSelected(null);
      alertMessage("Роли пользователя сохранены");
    } catch {
      alertMessage("Не удалось сохранить роли пользователя.");
    } finally {
      setSavingRoles(false);
    }
  }

  async function updateUser(user: UserListOut, patch: { is_active?: boolean; voice_assistant_enabled?: boolean }) {
    setBusyUserId(user.id);
    try {
      const updated = await usersApi.update(user.id, patch);
      setUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch {
      alertMessage("Не удалось изменить настройки пользователя.");
    } finally {
      setBusyUserId(null);
    }
  }

  const activeUsers = users.filter((user) => user.is_active).length;
  const voiceUsers = users.filter((user) => user.voice_assistant_enabled).length;

  return (
    <ConsoleShell
      title="Пользователи"
      subtitle="Учётные записи, доступ к системе, роли и голосовой помощник."
      actions={
        <button type="button" className="primary" onClick={openCreateDialog}>
          <Plus size={17} />
          Создать пользователя
        </button>
      }
    >
      <section className="users-panel">
        <div className="pane-heading">
          <div>
            <p className="eyebrow">Учётные записи</p>
            <h2>Все пользователи</h2>
          </div>
          {!loading && !loadError && (
            <div className="users-summary" aria-label="Сводка по пользователям">
              <span className="status-badge">{users.length} всего</span>
              <span className="status-badge success">{activeUsers} активных</span>
              <span className="status-badge">{voiceUsers} с голосом</span>
            </div>
          )}
        </div>

        {loading ? (
          <div className="empty-state">Загрузка пользователей...</div>
        ) : loadError ? (
          <div className="empty-state">
            <p className="error-text">{loadError}</p>
            <button type="button" onClick={() => window.location.reload()}>
              Повторить
            </button>
          </div>
        ) : users.length === 0 ? (
          <div className="empty-state">Пользователей пока нет.</div>
        ) : (
          <div className="users-table-scroll">
            <table className="order-table users-table">
              <thead>
                <tr>
                  <th>Пользователь</th>
                  <th>Роли</th>
                  <th>Статус</th>
                  <th>Голосовой помощник</th>
                  <th className="users-actions-heading">Действия</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => {
                  const busy = busyUserId === user.id;
                  return (
                    <tr key={user.id} className={user.is_active ? undefined : "muted-row"}>
                      <td>
                        <span className="user-identity">
                          <strong>{user.full_name}</strong>
                          <small>{user.email}</small>
                        </span>
                      </td>
                      <td>{user.role_names.join(", ") || "—"}</td>
                      <td>
                        <span className={`status-badge ${user.is_active ? "success" : "danger"}`}>
                          {user.is_active ? "Активен" : "Заблокирован"}
                        </span>
                      </td>
                      <td>
                        <span className="user-feature-status">
                          {user.voice_assistant_enabled ? <Mic size={16} /> : <MicOff size={16} />}
                          {user.voice_assistant_enabled ? "Включён" : "Выключён"}
                        </span>
                      </td>
                      <td>
                        <div className="users-actions">
                          <button type="button" onClick={() => selectUser(user)} disabled={busy}>
                            <ShieldCheck size={16} />
                            Роли
                          </button>
                          <button
                            type="button"
                            onClick={() => void updateUser(user, { is_active: !user.is_active })}
                            disabled={busy}
                          >
                            {user.is_active ? <UserX size={16} /> : <UserCheck size={16} />}
                            {user.is_active ? "Заблокировать" : "Активировать"}
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              void updateUser(user, { voice_assistant_enabled: !user.voice_assistant_enabled })
                            }
                            disabled={busy}
                          >
                            {user.voice_assistant_enabled ? <MicOff size={16} /> : <Mic size={16} />}
                            {user.voice_assistant_enabled ? "Выключить голос" : "Включить голос"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {createOpen && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => !creating && setCreateOpen(false)}>
          <form
            className="modal-card"
            onSubmit={(event) => void createUser(event)}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h2>Новый пользователь</h2>
                <p>Создайте учётную запись, а затем назначьте ей роли.</p>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={() => setCreateOpen(false)}
                disabled={creating}
                title="Закрыть"
              >
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <label className="modal-field">
                Email
                <input
                  autoFocus
                  type="email"
                  autoComplete="off"
                  value={userDraft.email}
                  onChange={(event) => setUserDraft((current) => ({ ...current, email: event.target.value }))}
                  disabled={creating}
                  required
                />
              </label>
              <label className="modal-field">
                Имя
                <input
                  value={userDraft.fullName}
                  onChange={(event) => setUserDraft((current) => ({ ...current, fullName: event.target.value }))}
                  disabled={creating}
                  required
                />
              </label>
              <label className="modal-field">
                Пароль
                <input
                  type="password"
                  autoComplete="new-password"
                  value={userDraft.password}
                  onChange={(event) => setUserDraft((current) => ({ ...current, password: event.target.value }))}
                  disabled={creating}
                  required
                />
              </label>
              {createError && <p className="error-text">{createError}</p>}
            </div>
            <div className="modal-footer">
              <button type="button" onClick={() => setCreateOpen(false)} disabled={creating}>
                Отмена
              </button>
              <button
                className="primary"
                type="submit"
                disabled={creating || !userDraft.email.trim() || !userDraft.fullName.trim() || !userDraft.password}
              >
                {creating ? "Создание..." : "Создать"}
              </button>
            </div>
          </form>
        </div>
      )}

      {selected && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => !savingRoles && setSelected(null)}>
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="user-roles-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h2 id="user-roles-title">Роли пользователя</h2>
                <p>{selected.full_name} · {selected.email}</p>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={() => setSelected(null)}
                disabled={savingRoles}
                title="Закрыть"
              >
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              {roles.length === 0 ? (
                <div className="empty-state">Роли ещё не созданы.</div>
              ) : (
                <div className="role-assignment-list">
                  {roles.map((role) => (
                    <label className="role-assignment-option" key={role.id}>
                      <input
                        type="checkbox"
                        checked={selectedRoleIds.includes(role.id)}
                        onChange={(event) =>
                          setSelectedRoleIds((current) =>
                            event.target.checked ? [...current, role.id] : current.filter((id) => id !== role.id),
                          )
                        }
                        disabled={savingRoles}
                      />
                      <span>
                        <strong>{role.name}</strong>
                        <small>{role.description || (role.is_system ? "Системная роль" : "Без описания")}</small>
                      </span>
                      {role.is_system && <span className="status-badge">system</span>}
                    </label>
                  ))}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button type="button" onClick={() => setSelected(null)} disabled={savingRoles}>
                Отмена
              </button>
              <button className="primary" type="button" onClick={() => void saveRoles()} disabled={savingRoles}>
                {savingRoles ? "Сохранение..." : "Сохранить роли"}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConsoleShell>
  );
}
