import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

// Storage keys for persisted auth data. New entries live under the `auth.` namespace.
const STORAGE_KEYS = {
  token: 'auth.token',
  user: 'auth.user',
};

// Legacy keys from the previous implementation. We clear these once migration happens.
const LEGACY_KEYS = {
  token: 'token',
  userId: 'userId',
  userEmail: 'userEmail',
};

// Helper to decode a JWT payload so we can read the `exp` claim. Invalid tokens
// are ignored and treated as non-expiring (the backend will still enforce auth).
function decodeJwtPayload(token) {
  if (!token) return null;
  const parts = token.split('.');
  if (parts.length < 2) return null;
  try {
    const payload = parts[1]
      .replace(/-/g, '+')
      .replace(/_/g, '/');
    const padded = payload.padEnd(payload.length + ((4 - (payload.length % 4)) % 4), '=');
    const decoded = atob(padded);
    return JSON.parse(decoded);
  } catch (err) {
    console.warn('Failed to decode JWT payload', err);
    return null;
  }
}

// Persist the current auth data to storage and clean up old keys.
function persistAuth(token, user) {
  try {
    if (token) {
      localStorage.setItem(STORAGE_KEYS.token, token);
    } else {
      localStorage.removeItem(STORAGE_KEYS.token);
    }
    if (user) {
      localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(user));
    } else {
      localStorage.removeItem(STORAGE_KEYS.user);
    }
    // Remove legacy entries to keep storage tidy.
    Object.values(LEGACY_KEYS).forEach((key) => localStorage.removeItem(key));
  } catch (err) {
    console.warn('Unable to persist auth data', err);
  }
}

// Remove both the new and legacy auth keys from storage.
function clearPersistedAuth() {
  try {
    Object.values(STORAGE_KEYS).forEach((key) => localStorage.removeItem(key));
    Object.values(LEGACY_KEYS).forEach((key) => localStorage.removeItem(key));
  } catch (err) {
    console.warn('Unable to clear auth data', err);
  }
}

// Load auth information from storage, migrating legacy keys when necessary.
function loadStoredAuth() {
  if (typeof window === 'undefined') {
    return { token: null, user: null, expiresAt: null };
  }

  let token = null;
  let user = null;
  let migrated = false;

  try {
    token = localStorage.getItem(STORAGE_KEYS.token);
    const rawUser = localStorage.getItem(STORAGE_KEYS.user);
    if (rawUser) {
      try {
        user = JSON.parse(rawUser);
      } catch {
        user = null;
      }
    }

    if (!token) {
      const legacyToken = localStorage.getItem(LEGACY_KEYS.token);
      if (legacyToken) {
        token = legacyToken;
        const legacyId = localStorage.getItem(LEGACY_KEYS.userId);
        const legacyEmail = localStorage.getItem(LEGACY_KEYS.userEmail);
        if (legacyId) {
          user = { id: legacyId, email: legacyEmail || '' };
        }
        migrated = true;
      }
    }
  } catch (err) {
    console.warn('Unable to read auth data', err);
    token = null;
    user = null;
  }

  const payload = decodeJwtPayload(token);
  const expiresAt = payload && typeof payload.exp === 'number' ? payload.exp * 1000 : null;
  const now = Date.now();

  if (token && expiresAt && expiresAt <= now) {
    clearPersistedAuth();
    return { token: null, user: null, expiresAt: null };
  }

  if (token && migrated) {
    persistAuth(token, user);
  }

  return { token, user, expiresAt };
}

const AuthContext = createContext(null);

// Provider exposing login/logout helpers and keeping auth state in sync with storage.
export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const [authState, setAuthState] = useState(() => loadStoredAuth());
  const loggingOut = useRef(false);

  const login = useCallback(({ token, user }) => {
    const payload = decodeJwtPayload(token);
    const expiresAt = payload && typeof payload.exp === 'number' ? payload.exp * 1000 : null;
    persistAuth(token, user);
    setAuthState({ token, user: user || null, expiresAt });
  }, []);

  const logout = useCallback(
    async ({ reason } = {}) => {
      if (loggingOut.current) return;
      loggingOut.current = true;
      try {
        clearPersistedAuth();
        setAuthState({ token: null, user: null, expiresAt: null });
        queryClient.removeQueries({ queryKey: ['user'] });
      } finally {
        loggingOut.current = false;
      }
    },
    [queryClient]
  );

  // When the stored token has an expiry timestamp, automatically clear it once
  // the time passes. This keeps the UI consistent without waiting for the next request.
  useEffect(() => {
    if (!authState.token || !authState.expiresAt) return;
    const now = Date.now();
    if (authState.expiresAt <= now) {
      logout({ reason: 'expired' });
      return;
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
      login,
      logout,
    }),
    [authState, login, logout]
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
