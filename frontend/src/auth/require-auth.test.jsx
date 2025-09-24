import '@testing-library/jest-dom';
import { render, screen, act } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createMemoryRouter, RouterProvider, Outlet, useLocation } from 'react-router-dom';
import RequireAuth from './RequireAuth.jsx';
import { AuthProvider } from './AuthContext.jsx';
import { createTestToken, setStoredAuth } from '../test-utils/auth.js';

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
    setStoredAuth({ token, user: { id: 'user-1', email: 'user@example.com' } });

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

    expect(await screen.findByText('Secret')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/en/secret');
  });
});
