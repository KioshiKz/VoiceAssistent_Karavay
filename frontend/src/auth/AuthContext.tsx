import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { authApi } from "../api/endpoints";
import { setAccessToken } from "../api/client";
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

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [permissions, setPermissions] = useState<MePermissions | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const token = await authApi.login(email, password);
      setAccessToken(token.access_token);
      setUser(token.user);
      const perms = await authApi.mePermissions();
      setPermissions(perms);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    setAccessToken(null);
    setUser(null);
    setPermissions(null);
    try {
      await authApi.logout();
    } catch {
      // best-effort: local state is already cleared
    }
  }, []);

  const hasTabView = useCallback(
    (tabKey: string) => permissions?.system_role || !!permissions?.tabs[tabKey]?.view,
    [permissions],
  );
  const hasTabEdit = useCallback(
    (tabKey: string) => permissions?.system_role || !!permissions?.tabs[tabKey]?.edit,
    [permissions],
  );
  const hasGlobal = useCallback(
    (code: string) => permissions?.system_role || !!permissions?.global[code],
    [permissions],
  );

  const updateVoiceAssistantEnabled = useCallback(async (enabled: boolean) => {
    const updated = await authApi.updateVoiceSettings(enabled);
    setUser(updated);
  }, []);

  const value = useMemo(
    () => ({
      user,
      permissions,
      isLoading,
      login,
      logout,
      hasTabView,
      hasTabEdit,
      hasGlobal,
      updateVoiceAssistantEnabled,
    }),
    [user, permissions, isLoading, login, logout, hasTabView, hasTabEdit, hasGlobal, updateVoiceAssistantEnabled],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
