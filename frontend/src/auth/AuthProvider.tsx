import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { authApi } from "../api/endpoints";
import { refreshSession, setAccessToken } from "../api/client";
import type { MePermissions, UserOut } from "../api/types";
import { AuthContext } from "./AuthContext";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [permissions, setPermissions] = useState<MePermissions | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const sessionGeneration = useRef(0);

  useEffect(() => {
    let active = true;
    const generation = sessionGeneration.current;
    const expired = () => { sessionGeneration.current += 1; setUser(null); setPermissions(null); setIsLoading(false); };
    window.addEventListener("auth-session-expired", expired);
    void refreshSession().then(async (token) => {
      const perms = await authApi.mePermissions();
      if (active && generation === sessionGeneration.current) { setUser(token.user); setPermissions(perms); }
    }).catch(() => {
      if (active && generation === sessionGeneration.current) { setUser(null); setPermissions(null); }
    }).finally(() => { if (active && generation === sessionGeneration.current) setIsLoading(false); });
    return () => { active = false; window.removeEventListener("auth-session-expired", expired); };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    sessionGeneration.current += 1;
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
    sessionGeneration.current += 1;
    setAccessToken(null);
    setUser(null);
    setPermissions(null);
    setIsLoading(false);
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

