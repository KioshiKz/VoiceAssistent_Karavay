import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import {
  Activity,
  Archive,
  CalendarClock,
  ClipboardList,
  Files,
  FolderTree,
  Home,
  LogOut,
  Mic,
  MicOff,
  ShieldCheck,
  Users,
} from "lucide-react";
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
    to: "/orders/upload",
    label: "Загрузка",
    icon: Files,
    canShow: (hasTabView: (key: string) => boolean) => hasTabView("upload_order"),
  },
  {
    to: "/orders/current",
    label: "Текущая заявка",
    icon: ClipboardList,
    canShow: (hasTabView: (key: string) => boolean) => hasTabView("current_order"),
  },
  {
    to: "/orders",
    label: "Все заявки",
    icon: Archive,
    canShow: (hasTabView: (key: string) => boolean) => hasTabView("orders_list"),
  },
  {
    to: "/monitoring",
    label: "Мониторинг",
    icon: Activity,
    canShow: (hasTabView: (key: string) => boolean) => hasTabView("order_monitoring"),
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
  const visibleItems = NAV_ITEMS.filter((item) => item.canShow(hasTabView, hasGlobal));
  const voiceEnabled = user?.voice_assistant_enabled !== false;

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
