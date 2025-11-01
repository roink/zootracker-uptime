// @ts-nocheck
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import '@testing-library/jest-dom';
import { act, render, screen } from '@testing-library/react';
import React from 'react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Dashboard from './Dashboard';
import { AuthProvider, useAuth } from '../auth/AuthContext';
import { loadLocale } from '../i18n';
import { createTestToken } from '../test-utils/auth';

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
    notes: 'Feeding time',
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
    expect(await screen.findByText('Note: Feeding time')).toBeInTheDocument();

    const achievementCalls = global.fetch.mock.calls.filter(([request]) =>
      typeof request === 'string' && request.includes('/achievements')
    );
    expect(achievementCalls).toHaveLength(0);

      await act(async () => {
        await loadLocale('de');
        await router.navigate('/de');
      });

    const german = await screen.findByText(
      'Löwe im Berlin Zoo am 2024-05-01 gesehen'
    );
    expect(german).toBeInTheDocument();
    expect(await screen.findByText('Notiz: Feeding time')).toBeInTheDocument();
  });
});

function AuthLogin({ auth, children }: any) {
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
