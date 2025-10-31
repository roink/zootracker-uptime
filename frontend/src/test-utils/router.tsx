// Utility to render components under a MemoryRouter for component tests
import type { PropsWithChildren, ReactElement, ReactNode } from 'react';
import { useEffect, useRef } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from '../auth/AuthContext';
import type { AuthSuccessPayload } from '../auth/AuthContext';
import { getStoredAuth } from './auth';

interface AuthSeedProps extends PropsWithChildren {
  auth: AuthSuccessPayload | null;
}

function AuthSeed({ auth, children }: AuthSeedProps): ReactNode {
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

type RenderWithRouterOptions = {
  route?: string;
  initialEntries?: string[];
  auth?: AuthSuccessPayload | null;
};

export function renderWithRouter(
  ui: ReactElement,
  { route = '/', initialEntries, auth }: RenderWithRouterOptions = {}
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

  const Wrapper = ({ children }: PropsWithChildren): ReactElement => (
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
