import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Archive, ClipboardList, FolderTree, Mic, ShieldCheck, Sparkles, Users } from "lucide-react";
import { foldersApi } from "../api/endpoints";
import type { FolderOut } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ConsoleShell } from "../components/ConsoleShell";

const SECTIONS = [
  {
    tabKey: "file_manager",
    path: "/files",
    title: "Файлы",
    description: "Дерево папок, ингредиенты, продукция и события производства.",
    icon: FolderTree,
  },
  {
    tabKey: "roles_permissions",
    globalCode: "admin.manage",
    path: "/admin/roles",
    title: "Роли и права",
    description: "Вкладки, папки, глобальные права и наследование доступа.",
    icon: ShieldCheck,
  },
  {
    tabKey: "users",
    globalCode: "admin.manage",
    path: "/admin/users",
    title: "Пользователи",
    description: "Пользователи, активность и назначение ролей.",
    icon: Users,
  },
  {
    tabKey: "current_order",
    path: "/orders/current",
    title: "Текущая заявка",
    description: "Просмотр очереди, сопоставление и запуск исполнения.",
    icon: ClipboardList,
  },
  {
    tabKey: "execution_queue",
    globalCode: "order.execute",
    path: "/execution",
    title: "Выполнение заявки",
    description: "Пошаговое выполнение текущей очереди с голосовыми командами и таймерами.",
    icon: Mic,
  },
];

export function Dashboard() {
  const { hasTabView, hasGlobal } = useAuth();
  const [workshops, setWorkshops] = useState<FolderOut[]>([]);

  useEffect(() => {
    if (!hasTabView("orders_list")) {
      setWorkshops([]);
      return;
    }
    foldersApi
      .tree()
      .then((folders) =>
        setWorkshops(
          folders
            .filter((folder) => folder.parent_id === null)
            .sort((a, b) => a.name.localeCompare(b.name, "ru")),
        ),
      )
      .catch(() => setWorkshops([]));
  }, [hasTabView]);

  const visibleStatic = SECTIONS.filter((section) => {
    if (section.tabKey === "execution_queue") return hasTabView(section.tabKey) && hasGlobal("order.execute");
    return section.globalCode ? hasTabView(section.tabKey) || hasGlobal(section.globalCode) : hasTabView(section.tabKey);
  });
  const visible = [
    ...visibleStatic,
    ...workshops.map((workshop) => ({
      tabKey: "orders_list",
      path: `/workshops/${workshop.id}/orders`,
      title: `Заявки: ${workshop.name}`,
      description: "Активные заявки, загрузка Excel и история заявок этого цеха.",
      icon: Archive,
    })),
  ];

  return (
    <ConsoleShell
      title="Главная консоль"
      subtitle="Быстрый доступ к файловой структуре, ролям, заявкам и исполнению производства."
    >
      <div className="dashboard-page">
        <section className="dashboard-hero">
          <div className="dashboard-panel">
            <p className="eyebrow">Рабочая область</p>
            <h2>Управление производственными данными без лишних шагов</h2>
            <p>
              Основной поток теперь собран вокруг папок и прав: файлы открываются с деревом слева,
              административные вкладки доступны справа, а создание сущностей вынесено в полноценные формы.
            </p>
            {visible[0] && (
              <div>
                <Link className="primary-button" to={visible[0].path}>
                  <Sparkles size={18} />
                  Открыть рабочий раздел
                </Link>
              </div>
            )}
          </div>

          <aside className="summary-panel">
            <h2>Структура</h2>
            <div className="summary-list">
              <span>
                <FolderTree size={17} />
                Дерево папок слева в файловом менеджере
              </span>
              <span>
                <ShieldCheck size={17} />
                Права и наследование в отдельной матрице
              </span>
              <span>
                <Archive size={17} />
                Отдельный список заявок для каждого доступного цеха
              </span>
            </div>
          </aside>
        </section>

        {visible.length === 0 ? (
          <div className="empty-state">Обратитесь к администратору за доступом к разделам.</div>
        ) : (
          <section className="dashboard-grid" aria-label="Разделы">
            {visible.map((section) => {
              const Icon = section.icon;
              return (
                <Link key={section.path} to={section.path} className="dashboard-card">
                  <div>
                    <h2>
                      <Icon size={18} />
                      {section.title}
                    </h2>
                    <p>{section.description}</p>
                  </div>
                  <span className="status-badge">Открыть</span>
                </Link>
              );
            })}
          </section>
        )}
      </div>
    </ConsoleShell>
  );
}
