import type { ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";

interface PermissionGateProps {
  children: ReactNode;
  tabEdit?: string;
  globalCode?: string;
  fallback?: ReactNode;
}

export function PermissionGate({ children, tabEdit, globalCode, fallback = null }: PermissionGateProps) {
  const { hasTabEdit, hasGlobal } = useAuth();

  if (tabEdit && !hasTabEdit(tabEdit)) return <>{fallback}</>;
  if (globalCode && !hasGlobal(globalCode)) return <>{fallback}</>;

  return <>{children}</>;
}
