import { createContext, useContext } from "react";
import type { MePermissions, UserOut } from "../api/types";

interface AuthContextValue {
  user: UserOut | null;
  permissions: MePermissions | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasTabView: (tabKey: string) => boolean;
  hasTabEdit: (tabKey: string) => boolean;
  hasGlobal: (code: string) => boolean;
  updateVoiceAssistantEnabled: (enabled: boolean) => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
