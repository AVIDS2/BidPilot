import { createContext, useContext, useState, useCallback, useEffect, useMemo, type ReactNode } from "react";
import { loginUser, registerUser, getCurrentUser, type CurrentUser } from "@/lib/api";

interface AuthState {
  user: CurrentUser | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, displayName: string, password: string) => Promise<void>;
  logout: () => void;
  setUser: (user: CurrentUser) => void;
}

const AuthContext = createContext<AuthState | null>(null);

const TOKEN_KEY = "docpilot_token";
const REFRESH_KEY = "docpilot_refresh_token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<CurrentUser | null>(null);

  // Fetch user info on mount when token exists
  useEffect(() => {
    if (token && !user) {
      getCurrentUser(token).then(setUser).catch(() => {
        // Token invalid, try refresh
        const refreshToken = localStorage.getItem(REFRESH_KEY);
        if (refreshToken) {
          fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8000"}/auth/refresh?refresh_token=${encodeURIComponent(refreshToken)}`, { method: "POST" })
            .then(r => r.ok ? r.json() : Promise.reject())
            .then((data: { access_token: string; refresh_token?: string }) => {
              localStorage.setItem(TOKEN_KEY, data.access_token);
              if (data.refresh_token) localStorage.setItem(REFRESH_KEY, data.refresh_token);
              setToken(data.access_token);
              return getCurrentUser(data.access_token);
            })
            .then(setUser)
            .catch(() => {
              localStorage.removeItem(TOKEN_KEY);
              localStorage.removeItem(REFRESH_KEY);
              setToken(null);
            });
        } else {
          localStorage.removeItem(TOKEN_KEY);
          setToken(null);
        }
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await loginUser({ email, password });
    localStorage.setItem(TOKEN_KEY, res.access_token);
    if (res.refresh_token) localStorage.setItem(REFRESH_KEY, res.refresh_token);
    setToken(res.access_token);
    const u = await getCurrentUser(res.access_token);
    setUser(u);
  }, []);

  const register = useCallback(async (email: string, displayName: string, password: string) => {
    await registerUser({ email, display_name: displayName, password });
    // Don't auto-login — user must verify email first
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo<AuthState>(() => ({
    user,
    token,
    isAuthenticated: !!token,
    login,
    register,
    logout,
    setUser,
  }), [user, token, login, register, logout]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
