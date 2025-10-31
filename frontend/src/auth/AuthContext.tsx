import type { PropsWithChildren } from 'react';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { API } from '../api';
import type { AuthUser } from '../types/domain';

const CSRF_COOKIE_NAME = 'refresh_csrf';
const CSRF_HEADER_NAME = 'X-CSRF';

type JwtPayload = {
  exp?: number;
  [key: string]: unknown;
};

type AuthState = {
  token: string | null;
  user: AuthUser | null;
  expiresAt: number | null;
  hydrated: boolean;
};

type AuthSuccessPayload = {
  token: string;
  user?: Partial<AuthUser> | null;
  expiresIn?: number | null;
};

type LogoutOptions = {
  reason?: string;
};

type RefreshResponse = {
  access_token: string;
  expires_in?: number | null;
  user_id: string;
  email_verified?: boolean;
};

type AuthContextValue = {
  token: string | null;
  user: AuthUser | null;
  tokenExpiresAt: number | null;
  isAuthenticated: boolean;
  hydrated: boolean;
  login: (payload: AuthSuccessPayload) => void;
  logout: (options?: LogoutOptions) => Promise<void>;
  refreshAccessToken: () => Promise<string>;
};

function decodeJwtPayload(token: string | null | undefined): JwtPayload | null {
  if (!token) return null;
  const parts = token.split('.');
  if (parts.length < 2) return null;
  try {
    const payloadSegment = parts[1]!;
    const payload = payloadSegment.replace(/-/g, '+').replace(/_/g, '/');
    const padded = payload.padEnd(payload.length + ((4 - (payload.length % 4)) % 4), '=');
    const decoded = atob(padded);
    return JSON.parse(decoded) as JwtPayload;
  } catch (err) {
    console.warn('Failed to decode JWT payload', err);
    return null;
  }
}

function computeExpiry(token: string | null | undefined, expiresIn?: number | null): number | null {
  if (!token) {
    return null;
  }
  const payload = decodeJwtPayload(token);
  if (payload && typeof payload.exp === 'number') {
    return payload.exp * 1000;
  }
  if (typeof expiresIn === 'number') {
    return Date.now() + expiresIn * 1000;
  }
  return null;
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const entries = document.cookie ? document.cookie.split('; ') : [];
  for (const entry of entries) {
    if (entry.startsWith(`${name}=`)) {
      return decodeURIComponent(entry.slice(name.length + 1));
    }
  }
  return null;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function mergeUser(current: AuthUser | null, patch?: Partial<AuthUser> | null): AuthUser | null {
  if (!patch) {
    return current;
  }
  const next: AuthUser = { ...(current ?? {}), ...patch };
  return Object.keys(next).length > 0 ? next : null;
}

export function AuthProvider({ children }: PropsWithChildren): JSX.Element {
  const queryClient = useQueryClient();
  const [authState, setAuthState] = useState<AuthState>({
    token: null,
    user: null,
    expiresAt: null,
    hydrated: false
  });
  const loggingOut = useRef(false);
  const refreshPromise = useRef<Promise<string> | null>(null);

  const clearAuthState = useCallback(() => {
    setAuthState((prev) => ({ ...prev, token: null, user: null, expiresAt: null, hydrated: true }));
    queryClient.clear();
  }, [queryClient]);

  const applyAuth = useCallback(
    (token: string | null | undefined, expiresIn?: number | null, userPatch?: Partial<AuthUser> | null) => {
      const resolvedToken = token ?? null;
      const expiresAt = computeExpiry(resolvedToken, expiresIn ?? null);
      setAuthState((prev) => {
        return {
          token: resolvedToken,
          user: mergeUser(prev.user, userPatch),
          expiresAt,
          hydrated: true
        };
      });
    },
    []
  );

  const login = useCallback(
    ({ token, user, expiresIn }: AuthSuccessPayload) => {
      applyAuth(token, expiresIn ?? null, user ?? null);
    },
    [applyAuth]
  );

  const logout = useCallback(
    async ({ reason: _reason }: LogoutOptions = {}) => {
      if (loggingOut.current) return;
      loggingOut.current = true;
      try {
        await fetch(`${API}/auth/logout`, { method: 'POST', credentials: 'include' });
      } catch (err) {
        console.warn('Logout request failed', err);
      } finally {
        clearAuthState();
        loggingOut.current = false;
      }
    },
    [clearAuthState]
  );

  const refreshAccessToken = useCallback(async () => {
    if (refreshPromise.current) {
      return refreshPromise.current;
    }
    const promise = (async () => {
      const csrfToken = readCookie(CSRF_COOKIE_NAME);
      if (!csrfToken) {
        throw new Error('Missing CSRF token');
      }
      const response = await fetch(`${API}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: { [CSRF_HEADER_NAME]: csrfToken }
      });
      if (!response.ok) {
        throw new Error(`Refresh failed with ${response.status}`);
      }
      const data = (await response.json()) as RefreshResponse;
      const userPatch: Partial<AuthUser> = { id: data.user_id };
      if (typeof data.email_verified === 'boolean') {
        userPatch.emailVerified = data.email_verified;
      }
      applyAuth(data.access_token, data.expires_in ?? null, userPatch);
      return data.access_token;
    })();
    refreshPromise.current = promise
      .catch((err) => {
        throw err;
      })
      .finally(() => {
        refreshPromise.current = null;
      });
    return refreshPromise.current;
  }, [applyAuth]);

  useEffect(() => {
    if (authState.hydrated) return;
    let active = true;
    refreshAccessToken()
      .catch(() => {
        if (active) {
          clearAuthState();
        }
      })
      .finally(() => {
        if (active) {
          setAuthState((prev) => (prev.hydrated ? prev : { ...prev, hydrated: true }));
        }
      });
    return () => {
      active = false;
    };
  }, [authState.hydrated, refreshAccessToken, clearAuthState]);

  useEffect(() => {
    if (!authState.token || !authState.expiresAt) return undefined;
    const now = Date.now();
    if (authState.expiresAt <= now) {
      void logout({ reason: 'expired' });
      return undefined;
    }
    const timeout = setTimeout(() => {
      void logout({ reason: 'expired' });
    }, authState.expiresAt - now);
    return () => clearTimeout(timeout);
  }, [authState.token, authState.expiresAt, logout]);

  const value = useMemo<AuthContextValue>(
    () => ({
      token: authState.token,
      user: authState.user,
      tokenExpiresAt: authState.expiresAt,
      isAuthenticated: Boolean(authState.token),
      hydrated: authState.hydrated,
      login,
      logout,
      refreshAccessToken
    }),
    [authState, login, logout, refreshAccessToken]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}

export { CSRF_HEADER_NAME };
export type { AuthContextValue, AuthSuccessPayload, LogoutOptions };
