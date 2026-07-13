import { useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import {
  Archive,
  CalendarClock,
  ClipboardList,
  FolderTree,
  Home,
  LogOut,
  Mic,
  MicOff,
  ShieldCheck,
  Users,
} from "lucide-react";
import { foldersApi } from "../api/endpoints";
import type { FolderOut } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { VoiceAssistant } from "./VoiceAssistant";

interface ConsoleShellProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
  actions?: ReactNode;
}

const NAV_ITEMS = [
  {
    to: "/",
    label: "Консоль",
    icon: Home,
    canShow: () => true,
  },
  {
    to: "/files",
    label: "Файлы",
    icon: FolderTree,
    canShow: (hasTabView: (key: string) => boolean) => hasTabView("file_manager"),
  },
  {
    to: "/admin/roles",
    label: "Роли и права",
    icon: ShieldCheck,
    canShow: (hasTabView: (key: string) => boolean, hasGlobal: (code: string) => boolean) =>
      hasTabView("roles_permissions") || hasGlobal("admin.manage"),
  },
  {
    to: "/admin/users",
    label: "Пользователи",
    icon: Users,
    canShow: (hasTabView: (key: string) => boolean, hasGlobal: (code: string) => boolean) =>
      hasTabView("users") || hasGlobal("admin.manage"),
  },
  {
    to: "/orders/current",
    label: "Текущая заявка",
    icon: ClipboardList,
    canShow: (hasTabView: (key: string) => boolean) => hasTabView("current_order"),
  },
  {
    to: "/execution",
    label: "Выполнение",
    icon: Mic,
    canShow: (hasTabView: (key: string) => boolean, hasGlobal: (code: string) => boolean) =>
      hasTabView("execution_queue") && hasGlobal("order.execute"),
  },
];

export function ConsoleShell({ title, subtitle, children, className, actions }: ConsoleShellProps) {
  const { user, hasTabView, hasGlobal, logout, updateVoiceAssistantEnabled } = useAuth();
  const [workshops, setWorkshops] = useState<FolderOut[]>([]);
  const visibleStaticItems = NAV_ITEMS.filter((item) => item.canShow(hasTabView, hasGlobal));
  const executionItems = visibleStaticItems.filter((item) => item.to === "/execution");
  const primaryItems = visibleStaticItems.filter((item) => item.to !== "/execution");
  const workshopItems = workshops.map((workshop) => ({
    to: `/workshops/${workshop.id}/orders`,
    label: `Заявки: ${workshop.name}`,
    icon: Archive,
  }));
  const visibleItems = [...primaryItems, ...workshopItems, ...executionItems];
  const voiceEnabled = user?.voice_assistant_enabled !== false;

  useEffect(() => {
    if (!hasTabView("orders_list")) {
      setWorkshops([]);
      return;
    }

    let active = true;
    foldersApi
      .tree()
      .then((folders) => {
        if (!active) return;
        setWorkshops(
          folders
            .filter((folder) => folder.parent_id === null)
            .sort((a, b) => a.name.localeCompare(b.name, "ru")),
        );
      })
      .catch(() => {
        if (active) setWorkshops([]);
      });

    return () => {
      active = false;
    };
  }, [hasTabView]);

  return (
    <div className="console-shell">
      <main className={`console-main${className ? ` ${className}` : ""}`}>
        <header className="console-header">
          <div>
            <p className="eyebrow">Karavay Production Console</p>
            <h1>{title}</h1>
            {subtitle && <p>{subtitle}</p>}
          </div>
          {actions && <div className="console-header-actions">{actions}</div>}
        </header>
        {children}
      </main>

      <aside className="console-rail">
        <div className="console-brand">
          <div className="brand-mark">
            <CalendarClock size={22} />
          </div>
          <div>
            <strong>Karavay</strong>
            <span>production</span>
          </div>
        </div>

        <nav className="console-tabs" aria-label="Разделы консоли">
          {visibleItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink key={item.to} to={item.to} end={item.to === "/"}>
                <Icon size={18} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="console-user">
          <span>{user?.full_name ?? "Пользователь"}</span>
          <button
            className="icon-button"
            type="button"
            onClick={() => void updateVoiceAssistantEnabled(!voiceEnabled)}
            title={voiceEnabled ? "Выключить голосового помощника" : "Включить голосового помощника"}
          >
            {voiceEnabled ? <Mic size={18} /> : <MicOff size={18} />}
          </button>
          <button className="icon-button" type="button" onClick={() => void logout()} title="Выйти">
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      <VoiceAssistant />
    </div>
  );
}
