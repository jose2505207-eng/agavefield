"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { getContext, getMe, logoutRequest, loginRequest, type AuthUser } from "@/lib/api";
import { guestContext, type OrgContext, type PermissionKey } from "@/lib/rbac";

type AuthState = {
  user: AuthUser | null;
  isDemo: boolean;
  loading: boolean;
  ctx: OrgContext | null;
  can: (perm: PermissionKey) => boolean;
  reload: () => Promise<void>;
  switchDemoProfile: (username: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState>({
  user: null,
  isDemo: false,
  loading: true,
  ctx: null,
  can: () => false,
  reload: async () => {},
  switchDemoProfile: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ctx, setCtx] = useState<OrgContext | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const me = await getMe();
      setUser(me);
      // The resolved membership/permissions/dashboard config is authoritative —
      // the backend computes it; the UI only renders from it.
      try {
        setCtx(await getContext());
      } catch {
        setCtx(guestContext(me));
      }
    } catch {
      setUser(null);
      setCtx(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function logout() {
    await logoutRequest();
    window.location.href = "/login";
  }

  // Demo-only: re-authenticate as a seeded demo profile (read-only) so the
  // backend resolves a different membership. Credentials are public by design.
  async function switchDemoProfile(username: string) {
    await loginRequest(username, username);
    window.location.href = "/";
  }

  const can = (perm: PermissionKey) => Boolean(ctx?.permissions?.[perm]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isDemo: Boolean(user?.is_demo),
        loading,
        ctx,
        can,
        reload: load,
        switchDemoProfile,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
