'use client';

import { useRouter } from 'next/navigation';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import * as api from '@/lib/api';
import { getToken } from '@/lib/auth';
import { ApiError, errorMessage } from '@/lib/errors';
import type { User } from '@/lib/types';

// 'unavailable': a token exists but the backend could not be reached to verify it.
type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated' | 'unavailable';

interface AuthContextValue {
  user: User | null;
  status: AuthStatus;
  /** Why the session could not be verified (status 'unavailable'). */
  error: string | null;
  /** Re-check the stored session, e.g. after the backend comes back. */
  retry: () => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  // Restore the session from a stored token on first load (and on retry).
  useEffect(() => {
    let cancelled = false;
    const restore = getToken() ? api.getCurrentUser() : Promise.reject(new ApiError('no token', 401));
    restore.then(
      (u) => {
        if (cancelled) return;
        setUser(u);
        setError(null);
        setStatus('authenticated');
      },
      (err) => {
        if (cancelled) return;
        setUser(null);
        // Only a 401 means the session is gone; anything else is a backend/network problem.
        if (err instanceof ApiError && err.status === 401) {
          setError(null);
          setStatus('unauthenticated');
        } else {
          setError(errorMessage(err));
          setStatus('unavailable');
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const retry = useCallback(() => {
    setStatus('loading');
    setAttempt((n) => n + 1);
  }, []);

  // Any API call that comes back 401 (expired/revoked session) logs out.
  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null);
      setStatus('unauthenticated');
    };
    window.addEventListener(api.UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(api.UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const u = await api.login(email, password);
    setUser(u);
    setError(null);
    setStatus('authenticated');
  }, []);

  const register = useCallback(
    async (email: string, password: string) => {
      await api.register(email, password);
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    await api.logout();
    setUser(null);
    setStatus('unauthenticated');
    router.push('/login');
  }, [router]);

  const value = useMemo(
    () => ({ user, status, error, retry, login, register, logout }),
    [user, status, error, retry, login, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
