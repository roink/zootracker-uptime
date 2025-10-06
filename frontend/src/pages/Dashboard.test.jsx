import React from 'react';
import '@testing-library/jest-dom';
import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Dashboard from './Dashboard.jsx';
import { loadLocale } from '../i18n.js';
import { AuthProvider, useAuth } from '../auth/AuthContext.jsx';
import { createTestToken } from '../test-utils/auth.js';

vi.mock('../hooks/useAuthFetch', () => ({ default: () => fetch }));
vi.mock('../components/Seo', () => ({ default: () => null }));

function renderDash(route, auth) {
  const client = new QueryClient();
  const router = createMemoryRouter(
    [
      {
        path: '/:lang',
        element: <Dashboard refresh={0} onUpdate={() => {}} />,
      },
    ],
    { initialEntries: [route] }
  );
  const utils = render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <AuthLogin auth={auth}>
          <RouterProvider router={router} />
        </AuthLogin>
      </AuthProvider>
    </QueryClientProvider>
  );
  return { ...utils, router };
}

describe('Dashboard', () => {
  const sighting = {
    id: 's1',
    zoo_id: 'z1',
    zoo_name: 'Berlin Zoo',
    animal_id: 'a1',
    animal_name_en: 'Lion',
    animal_name_de: 'Löwe',
    sighting_datetime: '2024-05-01T00:00:00Z',
    created_at: '2024-05-01T00:00:00Z',
  };

  let auth;

  beforeEach(() => {
    auth = { token: createTestToken(), user: { id: 'u1', email: 'user@example.com' }, expiresIn: 3600 };
    global.fetch = vi.fn(async (url) => {
      if (url.endsWith('/auth/refresh')) {
        return { ok: false, status: 401, json: () => Promise.resolve({}) };
      }
      if (url.endsWith('/auth/logout')) {
        return { ok: true, json: () => Promise.resolve({}) };
      }
      if (url.endsWith('/zoos')) return { ok: true, json: () => Promise.resolve([]) };
      if (url.endsWith('/animals')) return { ok: true, json: () => Promise.resolve([]) };
      if (url.endsWith('/visits')) return { ok: true, json: () => Promise.resolve([]) };
      if (url.includes('/animals/count'))
        return { ok: true, json: () => Promise.resolve({ count: 0 }) };
      if (url.endsWith('/sightings'))
        return { ok: true, json: () => Promise.resolve([sighting]) };
      if (url.endsWith('/achievements'))
        return { ok: true, json: () => Promise.resolve([]) };
      return { ok: true, json: () => Promise.resolve([]) };
    });
  });

  it('updates feed line when language changes', async () => {
    await loadLocale('en');
    const { router } = renderDash('/en', auth);
    const english = await screen.findByText(
      'Saw Lion at Berlin Zoo on 2024-05-01'
    );
    expect(english).toBeInTheDocument();

    await act(async () => {
      await loadLocale('de');
      router.navigate('/de');
    });

    const german = await screen.findByText(
      'Löwe im Berlin Zoo am 2024-05-01 gesehen'
    );
    expect(german).toBeInTheDocument();
  });
});

function AuthLogin({ auth, children }) {
  const { login, token, hydrated } = useAuth();

  React.useEffect(() => {
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
