import { useNavigate } from 'react-router-dom';
import { useCallback } from 'react';

// Hook returning a memoized fetch wrapper that automatically includes an
// Authorization header and redirects to the login page on HTTP 401.
export default function useAuthFetch(tokenFromProp) {
  const navigate = useNavigate();
  const token = tokenFromProp ?? localStorage.getItem('token');

  return useCallback(
    async (url, options = {}) => {
      const headers = new Headers(options.headers || {});
      if (token) headers.set('Authorization', `Bearer ${token}`);
      const resp = await fetch(url, { ...options, headers });
      if (resp.status === 401) {
        navigate('/login');
      }
      return resp;
    },
    [navigate, token]
  );
}
