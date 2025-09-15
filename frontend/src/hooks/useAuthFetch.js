import { useCallback, useRef } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';

// Hook returning a memoized fetch wrapper that automatically includes an
// Authorization header and clears auth state on HTTP 401 responses.
export default function useAuthFetch() {
  const { token, tokenExpiresAt, logout } = useAuth();
  const handling401 = useRef(false);

  return useCallback(
    async (input, options = {}) => {
      const headers = new Headers(options.headers || {});
      const now = Date.now();
      const hasValidToken = Boolean(token) && (!tokenExpiresAt || tokenExpiresAt > now);
      if (hasValidToken && !headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${token}`);
      }

      const response = await fetch(input, { ...options, headers });
      if (response.status !== 401) {
        return response;
      }

      if (handling401.current) {
        return response;
      }

      handling401.current = true;
      try {
        await logout({ reason: '401' });
      } finally {
        handling401.current = false;
      }
      return response;
    },
    [token, tokenExpiresAt, logout]
  );
}
