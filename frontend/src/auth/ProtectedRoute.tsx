import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

interface ProtectedRouteProps {
  children: ReactNode;
  tabView?: string;
  tabEdit?: string;
  globalCode?: string;
}

export function ProtectedRoute({ children, tabView, tabEdit, globalCode }: ProtectedRouteProps) {
  const { user, hasTabView, hasTabEdit, hasGlobal } = useAuth();

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (tabView && !hasTabView(tabView)) {
    return <div className="no-access">Нет доступа к этому разделу.</div>;
  }
  if (tabEdit && !hasTabEdit(tabEdit)) {
    return <div className="no-access">Нет доступа к этому разделу.</div>;
  }
  if (globalCode && !hasGlobal(globalCode)) {
    return <div className="no-access">Нет доступа к этому разделу.</div>;
  }

  return <>{children}</>;
}
