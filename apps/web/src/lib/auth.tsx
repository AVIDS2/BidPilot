import { createContext, useContext, useState, useCallback, useEffect, useMemo, type ReactNode } from "react";
import { loginUser, registerUser, getCurrentUser, verifyEmail, type CurrentUser } from "@/lib/api";
import { getStoredValue, removeStoredValue, setStoredValue } from "@/lib/browser-storage";

interface AuthState {
  user: CurrentUser | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string, turnstileToken?: string | null) => Promise<void>;
  completeEmailVerification: (token: string) => Promise<void>;
  register: (email: string, displayName: string, password: string, invitationToken?: string, orgName?: string, orgSlug?: string, turnstileToken?: string | null) => Promise<CurrentUser>;
  logout: () => void;
  setUser: (user: CurrentUser) => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => getStoredValue("token"));
  const [user, setUser] = useState<CurrentUser | null>(null);

  // Fetch user info on mount when token exists
  useEffect(() => {
    if (token && !user) {
      getCurrentUser(token).then(setUser).catch(() => {
        // Token invalid, try refresh
        const refreshToken = getStoredValue("refreshToken");
        if (refreshToken) {
          fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8000"}/auth/refresh?refresh_token=${encodeURIComponent(refreshToken)}`, { method: "POST" })
            .then(r => r.ok ? r.json() : Promise.reject())
            .then((data: { access_token: string; refresh_token?: string }) => {
              setStoredValue("token", data.access_token);
              if (data.refresh_token) setStoredValue("refreshToken", data.refresh_token);
              setToken(data.access_token);
              return getCurrentUser(data.access_token);
            })
            .then(setUser)
            .catch(() => {
              removeStoredValue("token");
              removeStoredValue("refreshToken");
              setToken(null);
            });
        } else {
          removeStoredValue("token");
          setToken(null);
        }
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const login = useCallback(async (email: string, password: string, turnstileToken?: string | null) => {
    const res = await loginUser({ email, password, turnstile_token: turnstileToken || null });
    setStoredValue("token", res.access_token);
    if (res.refresh_token) setStoredValue("refreshToken", res.refresh_token);
    setToken(res.access_token);
    const u = await getCurrentUser(res.access_token);
    setUser(u);
  }, []);

  const completeEmailVerification = useCallback(async (verificationToken: string) => {
    const res = await verifyEmail(verificationToken);
    setStoredValue("token", res.access_token);
    if (res.refresh_token) setStoredValue("refreshToken", res.refresh_token);
    setToken(res.access_token);
    setUser(await getCurrentUser(res.access_token));
  }, []);

  const register = useCallback(async (
    email: string,
    displayName: string,
    password: string,
    invitationToken?: string,
    orgName?: string,
    orgSlug?: string,
    turnstileToken?: string | null,
  ) => {
    return registerUser({
      email,
      display_name: displayName,
      password,
      invitation_token: invitationToken || null,
      org_name: orgName || null,
      org_slug: orgSlug || null,
      turnstile_token: turnstileToken || null,
    });
    // Don't auto-login — user must verify email first.
  }, []);

  const logout = useCallback(() => {
    removeStoredValue("token");
    removeStoredValue("refreshToken");
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo<AuthState>(() => ({
    user,
    token,
    isAuthenticated: !!token,
    login,
    completeEmailVerification,
    register,
    logout,
    setUser,
  }), [user, token, login, completeEmailVerification, register, logout]);

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
