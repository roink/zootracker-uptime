import { useCallback } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';

const REFRESH_THRESHOLD_MS = 60_000;

// Hook returning a memoized fetch wrapper that automatically refreshes access
// tokens, replays requests on 401 responses, and clears auth state if refresh
// attempts fail.
export default function useAuthFetch() {
  const { token, tokenExpiresAt, refreshAccessToken, logout } = useAuth();

  return useCallback(
    async (input, options = {}) => {
      const headers = new Headers(options.headers || {});
      let authToken = token;
      const now = Date.now();

      if (authToken && tokenExpiresAt && tokenExpiresAt - now < REFRESH_THRESHOLD_MS) {
        try {
          authToken = await refreshAccessToken();
        } catch (err) {
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
      } catch (err) {
        await logout({ reason: '401' });
        return response;
      }
    },
    [token, tokenExpiresAt, refreshAccessToken, logout]
  );
}
