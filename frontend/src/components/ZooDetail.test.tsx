// @ts-nocheck
import { screen, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import ZooDetail from './ZooDetail';
import { API } from '../api';
import { createTestToken } from '../test-utils/auth';
import { renderWithRouter } from '../test-utils/router';
import { toLocalYMD } from '../utils/sightingHistory';

vi.mock('./LazyMap', () => ({ default: () => <div data-testid="map" /> }));

const originalFetch = global.fetch;

describe('ZooDetail component', () => {
  const zoo = { id: 'z1', slug: 'test-zoo', name: 'Test Zoo', is_favorite: false };
  const userId = 'u1';
  const animalId = 'a1';
  const sightings = [
    {
      id: 's2',
      zoo_id: zoo.id,
      animal_id: 'a2',
      animal_name_en: 'Red Panda',
      animal_name_de: 'Kleiner Panda',
      zoo_name: zoo.name,
      sighting_datetime: '2022-06-02T15:05:00Z',
      created_at: '2022-06-02T15:10:00Z',
      notes: 'Sunny day',
    },
    {
      id: 's1',
      zoo_id: zoo.id,
      animal_id: animalId,
      animal_name_en: 'Lion',
      animal_name_de: 'Löwe',
      zoo_name: zoo.name,
      sighting_datetime: '2022-05-01T09:30:00Z',
      created_at: '2022-05-01T09:31:00Z',
      notes: null,
    },
  ];

  const jsonResponse = (data, status = 200) => ({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
  });

  const setupFetch = ({
    animals = [{ id: animalId, name_en: 'Lion', slug: 'lion', is_favorite: false }],
    visited = { visited: true },
    seen = [animalId],
    history = { items: sightings, total: sightings.length, limit: 50, offset: 0 },
  }: any = {}) => {
    global.fetch.mockImplementation((url, _options = {}) => {
      const requestUrl = typeof url === 'string' ? url : url?.url ?? '';
      if (requestUrl.endsWith('/auth/refresh')) {
        return Promise.resolve(jsonResponse({ detail: 'unauthorized' }, 401));
      }
      if (requestUrl.endsWith('/auth/logout')) {
        return Promise.resolve(jsonResponse({}));
      }
      if (requestUrl.endsWith(`/zoos/${zoo.slug}/animals`)) {
        return Promise.resolve(jsonResponse(animals));
      }
      if (requestUrl.endsWith(`/zoos/${zoo.slug}/visited`)) {
        return Promise.resolve(jsonResponse(visited));
      }
      if (requestUrl.endsWith(`/users/${userId}/animals/ids`)) {
        return Promise.resolve(jsonResponse(seen));
      }
      if (requestUrl.includes(`/zoos/${zoo.slug}/sightings`)) {
        if (history instanceof Promise) {
          return history;
        }
        return Promise.resolve(jsonResponse(history));
      }
      return Promise.resolve(jsonResponse([]));
    });
  };

  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    if (originalFetch) {
      global.fetch = originalFetch;
    } else {
      delete global.fetch;
    }
    vi.restoreAllMocks();
  });

  it('shows visit status, sighting history and notes', async () => {
    setupFetch();
    const token = createTestToken();
    renderWithRouter(<ZooDetail zoo={zoo} refresh={0} onLogged={() => {}} />, {
      auth: { token, user: { id: userId, email: 'user@example.com' }, expiresIn: 3600 },
      route: '/en/zoos/test-zoo',
    });

    await waitFor(() => {
      expect(screen.getByText('Visited? ☑️ Yes')).toBeInTheDocument();
      expect(screen.getByText('✔️')).toBeInTheDocument();
    });

    expect(await screen.findByText('Your visits at this zoo')).toBeInTheDocument();
    expect(screen.queryByText(/Log in or create an account/)).not.toBeInTheDocument();
    expect(screen.getByText(/You saw Red Panda at/)).toBeInTheDocument();
    expect(screen.getByText('Sunny day')).toBeInTheDocument();
    expect(screen.getByText(/You saw Lion/)).toBeInTheDocument();

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringMatching(`${API}/zoos/${zoo.slug}/visited`),
      expect.any(Object)
    );
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringMatching(`${API}/users/${userId}/animals/ids`),
      expect.any(Object)
    );
    const historyCall = global.fetch.mock.calls.find(([requestUrl]) =>
      typeof requestUrl === 'string' && requestUrl.endsWith(`/zoos/${zoo.slug}/sightings`)
    );
    expect(historyCall).toBeTruthy();
    const historyHeaders = historyCall?.[1]?.headers;
    const authHeader =
      typeof historyHeaders?.get === 'function'
        ? historyHeaders.get('Authorization')
        : historyHeaders?.Authorization;
    expect(authHeader).toMatch(/^Bearer /);
  });

  it('encourages login when history is unavailable', async () => {
    setupFetch();
    renderWithRouter(<ZooDetail zoo={zoo} refresh={0} onLogged={() => {}} />, {
      route: '/en/zoos/test-zoo',
    });

    expect(
      await screen.findByText(
        'Log in or create an account to see when you visited this zoo and which animals you saw.'
      )
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Log In / Sign Up' })).toBeInTheDocument();
  });

  it('shows loading state while history request is pending', async () => {
    let resolveHistory;
    const deferred = new Promise((resolve) => {
      resolveHistory = resolve;
    });
    setupFetch({ history: deferred });

    const token = createTestToken();
    renderWithRouter(<ZooDetail zoo={zoo} refresh={0} onLogged={() => {}} />, {
      auth: { token, user: { id: userId, email: 'user@example.com' }, expiresIn: 3600 },
      route: '/en/zoos/test-zoo',
    });

    expect(await screen.findByText('Loading your visit history…')).toBeInTheDocument();

    resolveHistory(jsonResponse({ items: sightings, total: sightings.length, limit: 50, offset: 0 }));
    await waitFor(() =>
      { expect(screen.queryByText('Loading your visit history…')).not.toBeInTheDocument(); }
    );
  });

  it('shows an error message when history fails to load', async () => {
    setupFetch({ history: Promise.resolve(jsonResponse({}, 500)) });

    const token = createTestToken();
    renderWithRouter(<ZooDetail zoo={zoo} refresh={0} onLogged={() => {}} />, {
      auth: { token, user: { id: userId, email: 'user@example.com' }, expiresIn: 3600 },
      route: '/en/zoos/test-zoo',
    });

    expect(
      await screen.findByText("We couldn't load your visit history for this zoo.")
    ).toBeInTheDocument();
  });

  it('shows an empty state when no history exists', async () => {
    setupFetch({ history: { items: [], total: 0, limit: 50, offset: 0 } });

    const token = createTestToken();
    renderWithRouter(<ZooDetail zoo={zoo} refresh={0} onLogged={() => {}} />, {
      auth: { token, user: { id: userId, email: 'user@example.com' }, expiresIn: 3600 },
      route: '/en/zoos/test-zoo',
    });

    expect(
      await screen.findByText("You haven't logged any sightings at this zoo yet.")
    ).toBeInTheDocument();
  });

  it('groups history by day and shows relative headings', async () => {
    const today = new Date();
    const isoToday = toLocalYMD(today);
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const isoYesterday = toLocalYMD(yesterday);
    const earlier = new Date(today);
    earlier.setDate(earlier.getDate() - 5);
    const isoEarlier = toLocalYMD(earlier);
    const historyData = {
      items: [
        {
          ...sightings[0],
          sighting_datetime: `${isoToday}T08:00:00Z`,
          created_at: `${isoToday}T09:00:00Z`,
        },
        {
          ...sightings[1],
          id: 's3',
          animal_id: animalId,
          animal_name_en: 'Lion',
          sighting_datetime: `${isoYesterday}T10:00:00Z`,
          created_at: `${isoYesterday}T11:00:00Z`,
        },
        {
          ...sightings[1],
          id: 's4',
          sighting_datetime: `${isoEarlier}T12:00:00Z`,
          created_at: `${isoEarlier}T12:30:00Z`,
        },
      ],
      total: 3,
      limit: 50,
      offset: 0,
    };
    setupFetch({ history: historyData });

    const token = createTestToken();
    renderWithRouter(<ZooDetail zoo={zoo} refresh={0} onLogged={() => {}} />, {
      auth: { token, user: { id: userId, email: 'user@example.com' }, expiresIn: 3600 },
      route: '/en/zoos/test-zoo',
    });

    expect(await screen.findByText('Today')).toBeInTheDocument();
    expect(screen.getByText('Yesterday')).toBeInTheDocument();
    const formatted = new Date(`${isoEarlier}T12:00:00`).toLocaleDateString('en-US');
    expect(screen.getByText(formatted)).toBeInTheDocument();
  });

  it('aborts the history request when the component unmounts', async () => {
    let historySignal;
    const historyPromise = new Promise(() => {});
    global.fetch.mockImplementation((url, options = {}) => {
      if (typeof url !== 'string') {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.endsWith('/auth/refresh')) {
        return Promise.resolve(jsonResponse({ detail: 'unauthorized' }, 401));
      }
      if (url.endsWith(`/zoos/${zoo.slug}/animals`)) {
        return Promise.resolve(jsonResponse([{ id: animalId, name_en: 'Lion' }]));
      }
      if (url.endsWith(`/zoos/${zoo.slug}/visited`)) {
        return Promise.resolve(jsonResponse({ visited: true }));
      }
      if (url.endsWith(`/users/${userId}/animals/ids`)) {
        return Promise.resolve(jsonResponse([animalId]));
      }
      if (url.includes(`/zoos/${zoo.slug}/sightings`)) {
        historySignal = options.signal;
        return historyPromise;
      }
      return Promise.resolve(jsonResponse([]));
    });

    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const token = createTestToken();
    const { unmount } = renderWithRouter(
      <ZooDetail zoo={zoo} refresh={0} onLogged={() => {}} />,
      {
        auth: { token, user: { id: userId, email: 'user@example.com' }, expiresIn: 3600 },
        route: '/en/zoos/test-zoo',
      }
    );

    await waitFor(() =>
      { expect(global.fetch).toHaveBeenCalledWith(
        expect.stringMatching(`${API}/zoos/${zoo.slug}/sightings`),
        expect.any(Object)
      ); }
    );

    unmount();
    expect(historySignal?.aborted).toBe(true);

    await act(async () => {
      await Promise.resolve();
    });
    expect(errorSpy).not.toHaveBeenCalled();
    errorSpy.mockRestore();
  });
});
