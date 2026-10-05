// Handles frontend authentication state (token storage only).
//
// The backend issues an opaque bearer session token (POST /api/auth/login).
// It is kept in localStorage and sent as `Authorization: Bearer <token>`.
// React state for the logged-in user lives in components/auth/AuthProvider.

import type { TokenResponse } from './types';

const TOKEN_KEY = 'mia.token';

interface StoredToken {
  access_token: string;
  expires_at: string;
}

export function saveToken(token: TokenResponse): void {
  const stored: StoredToken = { access_token: token.access_token, expires_at: token.expires_at };
  try {
    localStorage.setItem(TOKEN_KEY, JSON.stringify(stored));
  } catch {
    // Storage unavailable (private mode etc.) - session will not persist.
  }
}

export function getToken(): string | null {
  try {
    const raw = localStorage.getItem(TOKEN_KEY);
    if (!raw) return null;
    const stored = JSON.parse(raw) as StoredToken;
    if (new Date(stored.expires_at).getTime() <= Date.now()) {
      clearToken();
      return null;
    }
    return stored.access_token;
  } catch {
    return null;
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore
  }
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}
