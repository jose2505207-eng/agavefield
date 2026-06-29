"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { getMe, logoutRequest, type AuthUser } from "@/lib/api";

type AuthState = {
  user: AuthUser | null;
  isDemo: boolean;
  loading: boolean;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState>({
  user: null,
  isDemo: false,
  loading: true,
  logout: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  async function logout() {
    await logoutRequest();
    window.location.href = "/login";
  }

  return (
    <AuthContext.Provider value={{ user, isDemo: Boolean(user?.is_demo), loading, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
