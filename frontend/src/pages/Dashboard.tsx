import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const SECTIONS: { tabKey: string; path: string; title: string; description: string }[] = [
  { tabKey: "file_manager", path: "/files", title: "Файлы", description: "Папки, ингредиенты, продукция, события" },
  { tabKey: "roles_permissions", path: "/admin/roles", title: "Роли и права", description: "Настройка ролей и доступа" },
  { tabKey: "users", path: "/admin/users", title: "Пользователи", description: "Управление пользователями" },
  { tabKey: "upload_order", path: "/orders/upload", title: "Загрузить заявку", description: "Загрузка Excel-заявки" },
  { tabKey: "current_order", path: "/orders/current", title: "Текущая заявка", description: "Просмотр и исполнение заявки" },
];

export function Dashboard() {
  const { user, hasTabView, logout } = useAuth();
  const visible = SECTIONS.filter((s) => hasTabView(s.tabKey));

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <h1>Karavay Production Console</h1>
        <div>
          <span>{user?.full_name}</span>
          <button onClick={() => logout()}>Выйти</button>
        </div>
      </div>
      {visible.length === 0 ? (
        <p>Обратитесь к администратору за доступом к разделам.</p>
      ) : (
        <div className="dashboard-grid">
          {visible.map((s) => (
            <Link key={s.tabKey} to={s.path} className="dashboard-card">
              <h2>{s.title}</h2>
              <p>{s.description}</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
