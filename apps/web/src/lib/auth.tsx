'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode
} from 'react';
import { usePathname } from 'next/navigation';

export interface CurrentUser {
  id: string;
  email: string;
  display_name: string;
  role: string;
  plan?: string;
  disabled?: boolean;
  email_verified?: boolean;
  org_id?: string;
  org_slug?: string;
  verification_email_accepted?: boolean | null;
}

export interface UserRegister {
  email: string;
  display_name: string;
  password: string;
  invitation_token?: string | null;
  org_name?: string | null;
  org_slug?: string | null;
  turnstile_token?: string | null;
}

type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

interface AuthContextValue {
  user: CurrentUser | null;
  status: AuthStatus;
  isAuthenticated: boolean;
  refresh: () => Promise<CurrentUser | null>;
  login: (email: string, password: string, turnstileToken?: string | null) => Promise<CurrentUser>;
  register: (payload: UserRegister) => Promise<CurrentUser>;
  logout: () => Promise<void>;
  setUser: (user: CurrentUser | null) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function readApiError(response: Response) {
  try {
    const body = (await response.json()) as { message?: unknown; detail?: unknown };
    if (typeof body.message === 'string') return body.message;
    if (typeof body.detail === 'string') return body.detail;
  } catch {
    // A non-JSON response is still represented by its HTTP status.
  }
  return `请求失败（${response.status}）`;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const needsSession =
    pathname !== '/' &&
    pathname !== '/pricing' &&
    pathname !== '/docs' &&
    !pathname.startsWith('/auth');
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [checkedPathname, setCheckedPathname] = useState<string | null>(null);
  const sessionCheckStarted = useRef(false);
  const checkedPathnameRef = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    let response = await fetch('/api/auth/me', { cache: 'no-store' });
    if (response.status === 401) {
      const renewed = await fetch('/api/auth/refresh', { method: 'POST' });
      if (renewed.ok) response = await fetch('/api/auth/me', { cache: 'no-store' });
    }
    if (!response.ok) {
      setUser(null);
      setStatus('unauthenticated');
      return null;
    }
    const nextUser = (await response.json()) as CurrentUser;
    setUser(nextUser);
    setStatus('authenticated');
    return nextUser;
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!needsSession) {
      if (pathname.startsWith('/auth')) {
        setUser(null);
        setStatus('unauthenticated');
      }
      checkedPathnameRef.current = pathname;
      setCheckedPathname(pathname);
      return () => {
        cancelled = true;
      };
    }
    // Reuse the current session across client route changes instead of
    // re-fetching /me for every page, which made navigation feel like a reload.
    if (checkedPathnameRef.current === pathname) return;
    if (sessionCheckStarted.current) {
      checkedPathnameRef.current = pathname;
      setCheckedPathname(pathname);
      return;
    }
    sessionCheckStarted.current = true;
    checkedPathnameRef.current = pathname;
    setCheckedPathname(pathname);
    setStatus('loading');
    void refresh()
      .catch(() => {
        if (!cancelled) {
          setUser(null);
          setStatus('unauthenticated');
        }
      })
      .finally(() => {
        if (!cancelled) {
          checkedPathnameRef.current = pathname;
          setCheckedPathname(pathname);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [needsSession, pathname, refresh]);

  const visibleStatus: AuthStatus =
    needsSession && checkedPathname !== pathname ? 'loading' : status;

  const login = useCallback(
    async (email: string, password: string, turnstileToken?: string | null) => {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, turnstile_token: turnstileToken ?? null })
      });
      if (!response.ok) throw new Error(await readApiError(response));
      const nextUser = await refresh();
      if (!nextUser) throw new Error('登录成功，但无法读取当前账户。');
      return nextUser;
    },
    [refresh]
  );

  const register = useCallback(async (payload: UserRegister) => {
    const response = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(await readApiError(response));
    return (await response.json()) as CurrentUser;
  }, []);

  const logout = useCallback(async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    setUser(null);
    setStatus('unauthenticated');
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      status: visibleStatus,
      isAuthenticated: visibleStatus === 'authenticated',
      refresh,
      login,
      register,
      logout,
      setUser
    }),
    [user, visibleStatus, refresh, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
