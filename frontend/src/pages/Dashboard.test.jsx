import React from 'react';
import '@testing-library/jest-dom';
import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Dashboard from './Dashboard.jsx';
import { loadLocale } from '../i18n.js';
import { AuthProvider } from '../auth/AuthContext.jsx';
import { createTestToken, setStoredAuth } from '../test-utils/auth.js';

vi.mock('../hooks/useAuthFetch', () => ({ default: () => fetch }));
vi.mock('../components/Seo', () => ({ default: () => null }));

function renderDash(route) {
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
        <RouterProvider router={router} />
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

  beforeEach(() => {
    const token = createTestToken();
    setStoredAuth({ token, user: { id: 'u1', email: 'user@example.com' } });
    global.fetch = vi.fn(async (url) => {
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
    const { router } = renderDash('/en');
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
