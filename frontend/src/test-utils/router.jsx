// Utility to render components under a MemoryRouter for component tests
import { useEffect, useRef } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from '../auth/AuthContext.jsx';
import { getStoredAuth } from './auth.js';

function AuthSeed({ auth, children }) {
  const { login, token, hydrated } = useAuth();
  const seededRef = useRef(false);

  useEffect(() => {
    if (auth && auth.token && !seededRef.current) {
      login(auth);
      seededRef.current = true;
    }
  }, [auth, login]);

  if (auth?.token) {
    if (!seededRef.current || !token) {
      return null;
    }
  } else if (!hydrated) {
    return null;
  }

  return children;
}

export function renderWithRouter(
  ui,
  { route = '/', initialEntries, auth } = {}
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  const entries = initialEntries ?? [route];
  const authConfig = auth ?? getStoredAuth();

  const Wrapper = ({ children }) => (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AuthSeed auth={authConfig}>
          <MemoryRouter initialEntries={entries}>
            {children}
          </MemoryRouter>
        </AuthSeed>
      </AuthProvider>
    </QueryClientProvider>
  );

  return render(ui, { wrapper: Wrapper });
}
