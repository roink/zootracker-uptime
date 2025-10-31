import { useCallback } from 'react';
import { useAuth } from '../auth/AuthContext';

const REFRESH_THRESHOLD_MS = 60_000;

type FetchInput = Parameters<typeof fetch>[0];
type FetchInit = Parameters<typeof fetch>[1];

export default function useAuthFetch() {
  const { token, tokenExpiresAt, refreshAccessToken, logout } = useAuth();

  return useCallback(
    async (input: FetchInput, options: FetchInit = {}): Promise<Response> => {
      const headers = new Headers(options?.headers ?? {});
      let authToken = token ?? null;
      const now = Date.now();

      if (authToken && tokenExpiresAt && tokenExpiresAt - now < REFRESH_THRESHOLD_MS) {
        try {
          authToken = await refreshAccessToken();
        } catch {
          await logout({ reason: 'refresh_failed' });
          return fetch(input, { ...options, headers });
        }
      }

      if (authToken && !headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${authToken}`);
      }

      let response = await fetch(input, { ...options, headers });
      if (response.status !== 401) {
        return response;
      }

      try {
        const refreshed = await refreshAccessToken();
        if (!refreshed) {
          await logout({ reason: '401' });
          return response;
        }
        headers.set('Authorization', `Bearer ${refreshed}`);
        response = await fetch(input, { ...options, headers });
        if (response.status === 401) {
          await logout({ reason: '401' });
        }
        return response;
      } catch {
        await logout({ reason: '401' });
        return response;
      }
    },
    [token, tokenExpiresAt, refreshAccessToken, logout]
  );
}
