"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { apiFetch, clearStoredToken, getStoredToken, storeToken } from "@/lib/api";
import type { LoginResponse, User } from "@/lib/types";

type AuthState = "loading" | "signed_in" | "signed_out";

interface AuthContextValue {
  user: User | null;
  state: AuthState;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [state, setState] = useState<AuthState>("loading");

  const refreshUser = useCallback(async () => {
    const token = getStoredToken();
    if (!token) {
      setUser(null);
      setState("signed_out");
      return;
    }
    try {
      const current = await apiFetch<User>("/auth/me");
      setUser(current);
      setState("signed_in");
    } catch {
      clearStoredToken();
      setUser(null);
      setState("signed_out");
    }
  }, []);

  useEffect(() => {
    // Session hydration reads a token from localStorage and verifies it with
    // the API. The state update is the result of that external-system read.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshUser();
  }, [refreshUser]);

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === "civicops.session") void refreshUser();
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [refreshUser]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await apiFetch<LoginResponse>("/auth/login", {
      method: "POST",
      body: { email, password },
    });
    storeToken(response.access_token);
    setUser(response.user);
    setState("signed_in");
    return response.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch {
      // Local sign-out should still work if the server is unreachable.
    }
    clearStoredToken();
    setUser(null);
    setState("signed_out");
  }, []);

  const value = useMemo(
    () => ({ user, state, login, logout, refreshUser }),
    [user, state, login, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider.");
  return context;
}
