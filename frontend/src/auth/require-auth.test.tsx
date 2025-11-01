// @ts-nocheck
import '@testing-library/jest-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, act } from '@testing-library/react';
import { useEffect } from 'react';
import { createMemoryRouter, RouterProvider, Outlet, useLocation } from 'react-router-dom';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { AuthProvider, useAuth } from './AuthContext';
import RequireAuth from './RequireAuth';
import { createTestToken } from '../test-utils/auth';

function Layout() {
  return <Outlet />;
}

function LoginCapture() {
  const location = useLocation();
  return (
    <div data-testid="login-page" data-from={location.state?.from?.pathname || ''}>
      Login
    </div>
  );
}

describe('RequireAuth', () => {
  beforeEach(() => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: false, status: 401, json: () => Promise.resolve({}) }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('redirects unauthenticated users to login and preserves from', async () => {
    const client = new QueryClient();
    const router = createMemoryRouter(
      [
        {
          path: '/:lang/*',
          element: <Layout />,
          children: [
            {
              element: <RequireAuth />,
              children: [{ path: 'secret', element: <div>Secret</div> }],
            },
            { path: 'login', element: <LoginCapture /> },
          ],
        },
      ],
      { initialEntries: ['/en/secret'] }
    );

    render(
      <QueryClientProvider client={client}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </QueryClientProvider>
    );

    const login = await screen.findByTestId('login-page');
    expect(login).toBeInTheDocument();
    expect(login.dataset.from).toBe('/en/secret');
    expect(router.state.location.pathname).toBe('/en/login');

    await act(async () => {
      await router.navigate(-1);
    });

    expect(router.state.location.pathname).toBe('/en/login');
  });

  it('allows access when authenticated', async () => {
    const client = new QueryClient();
    const token = createTestToken();
    const auth = { token, user: { id: 'user-1', email: 'user@example.com' }, expiresIn: 3600 };

    const router = createMemoryRouter(
      [
        {
          path: '/:lang/*',
          element: <Layout />,
          children: [
            {
              element: <RequireAuth />,
              children: [{ path: 'secret', element: <div>Secret</div> }],
            },
            { path: 'login', element: <LoginCapture /> },
          ],
        },
      ],
      { initialEntries: ['/en/secret'] }
    );

    render(
      <QueryClientProvider client={client}>
        <AuthProvider>
          <AuthLogin auth={auth}>
            <RouterProvider router={router} />
          </AuthLogin>
        </AuthProvider>
      </QueryClientProvider>
    );

    expect(await screen.findByText('Secret')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/en/secret');
  });
});

function AuthLogin({ auth, children }: any) {
  const { login, token, hydrated } = useAuth();

  useEffect(() => {
    if (auth?.token) {
      login(auth);
    }
  }, [auth, login]);

  if (auth?.token && !token) {
    return null;
  }
  if (!auth?.token && !hydrated) {
    return null;
  }
  return children;
}
