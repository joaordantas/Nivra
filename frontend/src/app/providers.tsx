import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { api } from "../services/api";
import type { User } from "../types";

const THEME_STORAGE_KEY = "financas-theme";

export type Theme = "light" | "dark";

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (user: User) => void;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const ThemeContext = createContext<{
  theme: Theme;
  toggleTheme: () => void;
} | null>(null);

function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    const savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (savedTheme === "light" || savedTheme === "dark") return savedTheme;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const value = useMemo(
    () => ({
      theme,
      toggleTheme: () => setTheme((current) => current === "light" ? "dark" : "light"),
    }),
    [theme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const refreshUser = useCallback(async () => setUser(await api.getCurrentUser()), []);

  useEffect(() => {
    let active = true;
    async function restoreSession() {
      window.localStorage.removeItem("controle-financas-user");
      try {
        const currentUser = await api.getCurrentUser();
        if (active) setUser(currentUser);
      } catch {
        if (active) setUser(null);
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void restoreSession();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const clearUnauthorizedSession = () => {
      setUser(null);
      setIsLoading(false);
    };
    window.addEventListener("nivra:unauthorized", clearUnauthorizedSession);
    return () => window.removeEventListener("nivra:unauthorized", clearUnauthorizedSession);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: Boolean(user),
      isLoading,
      login: setUser,
      refreshUser,
      logout: async () => {
        try {
          await api.logout();
        } finally {
          setUser(null);
        }
      },
    }),
    [isLoading, refreshUser, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function AppProviders({ children }: { children: ReactNode }) {
  return <ThemeProvider><AuthProvider>{children}</AuthProvider></ThemeProvider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth precisa ser usado dentro de AppProviders.");
  }

  return context;
}

export function useTheme() {
  const context = useContext(ThemeContext);

  if (!context) {
    throw new Error("useTheme precisa ser usado dentro de AppProviders.");
  }

  return context;
}
