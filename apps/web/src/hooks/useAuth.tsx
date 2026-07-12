"use client";

/**
 * Session state: resolves the stored token to a user on mount, exposes
 * sign-in/sign-up/sign-out. Wraps the app in layout.tsx so the topbar,
 * follow flow, and portfolio all share one session.
 *
 * States: loading (token being resolved) → user | null. An invalid or
 * expired token is cleared silently — the UI just renders signed-out.
 */
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

import {
  apiLogin,
  apiRefresh,
  apiRegister,
  clearToken,
  fetchMe,
  getToken,
  setSession,
} from "@/lib/auth";
import type { ApiUser } from "@/lib/types";

export type AuthMode = "login" | "register";

interface AuthContextValue {
  user: ApiUser | null;
  loading: boolean;
  signIn: (email: string, password: string, mode: AuthMode) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  signIn: async () => {
    throw new Error("AuthProvider missing");
  },
  signOut: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<ApiUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let unmounted = false;
    if (!getToken()) {
      setLoading(false);
      return;
    }
    // Expired access token? Try the refresh token once before giving up —
    // access tokens now live 24h, refresh tokens 30d.
    fetchMe()
      .catch(async () => {
        const refreshed = await apiRefresh();
        if (!refreshed) throw new Error("session expired");
        return fetchMe();
      })
      .then((me) => {
        if (!unmounted) setUser(me);
      })
      .catch(() => {
        clearToken();
      })
      .finally(() => {
        if (!unmounted) setLoading(false);
      });
    return () => {
      unmounted = true;
    };
  }, []);

  const signIn = useCallback(
    async (email: string, password: string, mode: AuthMode) => {
      const call = mode === "register" ? apiRegister : apiLogin;
      const result = await call(email, password);
      setSession(result);
      setUser(result.user);
    },
    [],
  );

  const signOut = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
