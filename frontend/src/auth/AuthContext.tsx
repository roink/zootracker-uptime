// @ts-nocheck
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { API } from '../api';

const CSRF_COOKIE_NAME = 'refresh_csrf';
const CSRF_HEADER_NAME = 'X-CSRF';

function decodeJwtPayload(token) {
  if (!token) return null;
  const parts = token.split('.');
  if (parts.length < 2) return null;
  try {
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = payload.padEnd(payload.length + ((4 - (payload.length % 4)) % 4), '=');
    const decoded = atob(padded);
    return JSON.parse(decoded);
  } catch (err) {
    console.warn('Failed to decode JWT payload', err);
    return null;
  }
}

function computeExpiry(token, expiresIn) {
  const payload = decodeJwtPayload(token);
  if (payload && typeof payload.exp === 'number') {
    return payload.exp * 1000;
  }
  if (typeof expiresIn === 'number') {
    return Date.now() + expiresIn * 1000;
  }
  return null;
}

function readCookie(name) {
  if (typeof document === 'undefined') return null;
  const entries = document.cookie ? document.cookie.split('; ') : [];
  for (const entry of entries) {
    if (entry.startsWith(`${name}=`)) {
      return decodeURIComponent(entry.slice(name.length + 1));
    }
  }
  return null;
}

const AuthContext = createContext<any>(null);

export function AuthProvider({ children }: any) {
  const queryClient = useQueryClient();
  const [authState, setAuthState] = useState({
    token: null,
    user: null,
    expiresAt: null,
    hydrated: false,
  });
  const loggingOut = useRef(false);
  const refreshPromise = useRef<any>(null);

  const clearAuthState = useCallback(() => {
    setAuthState((prev) => ({ ...prev, token: null, user: null, expiresAt: null, hydrated: true }));
    queryClient.clear();
  }, [queryClient]);

  const applyAuth = useCallback((token, expiresIn, userPatch) => {
    const expiresAt = computeExpiry(token, expiresIn);
    setAuthState((prev) => {
      const mergedUser = userPatch
        ? { ...(prev.user ?? {}), ...userPatch }
        : prev.user;
      return {
        token,
        user: mergedUser ?? null,
        expiresAt,
        hydrated: true,
      };
    });
  }, []);

  const login = useCallback(
    ({ token, user, expiresIn }: any) => {
      applyAuth(token, expiresIn, user);
    },
    [applyAuth]
  );

  const logout = useCallback(
    async ({ reason }: any = {}) => {
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
        headers: { [CSRF_HEADER_NAME]: csrfToken },
      });
      if (!response.ok) {
        throw new Error(`Refresh failed with ${response.status}`);
      }
      const data = await response.json();
      applyAuth(data.access_token, data.expires_in, { id: data.user_id, emailVerified: data.email_verified });
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
      logout({ reason: 'expired' });
      return undefined;
    }
    const timeout = setTimeout(() => logout({ reason: 'expired' }), authState.expiresAt - now);
    return () => clearTimeout(timeout);
  }, [authState.token, authState.expiresAt, logout]);

  const value = useMemo(
    () => ({
      token: authState.token,
      user: authState.user,
      tokenExpiresAt: authState.expiresAt,
      isAuthenticated: Boolean(authState.token),
      hydrated: authState.hydrated,
      login,
      logout,
      refreshAccessToken,
    }),
    [authState, login, logout, refreshAccessToken]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}

export { CSRF_HEADER_NAME };
