import { screen, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import ZooDetail, { type ZooDetailData } from './ZooDetail';
import { API } from '../api';
import { createTestToken } from '../test-utils/auth';
import { renderWithRouter } from '../test-utils/router';
import type { Sighting } from '../types/domain';
import { toLocalYMD } from '../utils/sightingHistory';

vi.mock('./LazyMap', () => ({ default: () => <div data-testid="map" /> }));

const originalFetch = global.fetch;
const fetchMock = vi.fn<typeof fetch>();

describe('ZooDetail component', () => {
  const zoo: ZooDetailData = { id: 'z1', slug: 'test-zoo', name: 'Test Zoo', latitude: 0, longitude: 0, city: null, is_favorite: false };
  const userId = 'u1';
  const animalId = 'a1';
  const sightings: Sighting[] = [
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

const jsonResponse = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const isHeaderRecord = (value: HeadersInit): value is Record<string, string> => {
  return !(value instanceof Headers) && !Array.isArray(value);
};

  const setupFetch = ({
    animals = [{ id: animalId, name_en: 'Lion', slug: 'lion', is_favorite: false }],
    visited = { visited: true },
    seen = [animalId],
    history = { items: sightings, total: sightings.length, limit: 50, offset: 0 },
  }: {
    animals?: Array<Record<string, unknown>>;
    visited?: { visited?: boolean };
    seen?: string[];
    history?: Response | Promise<Response> | { items?: unknown; total?: number; limit?: number; offset?: number };
  } = {}) => {
    fetchMock.mockImplementation((request: RequestInfo | URL, _options: RequestInit = {}) => {
      const requestUrl =
        typeof request === 'string'
          ? request
          : request instanceof URL
            ? request.toString()
            : request.url;
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
        if (history instanceof Response) {
          return Promise.resolve(history);
        }
        return Promise.resolve(jsonResponse(history));
      }
      return Promise.resolve(jsonResponse([]));
    });
  };

  beforeEach(() => {
    fetchMock.mockReset();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
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

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(`${API}/zoos/${zoo.slug}/visited`),
      expect.any(Object)
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(`${API}/users/${userId}/animals/ids`),
      expect.any(Object)
    );
    let historyCall: [RequestInfo | URL, RequestInit?] | undefined;
    const fetchCalls = fetchMock.mock.calls as Array<[RequestInfo | URL, RequestInit?]>;
    for (const call of fetchCalls) {
      const [request] = call;
      const requestUrl =
        typeof request === 'string'
          ? request
          : request instanceof URL
            ? request.toString()
            : request.url;
      if (typeof requestUrl === 'string' && requestUrl.endsWith(`/zoos/${zoo.slug}/sightings`)) {
        historyCall = call;
        break;
      }
    }
    expect(historyCall).toBeDefined();
    const historyHeaders = historyCall?.[1]?.headers;
    let authHeader: string | undefined;
    if (historyHeaders instanceof Headers) {
      authHeader = historyHeaders.get('Authorization') ?? undefined;
    } else if (Array.isArray(historyHeaders)) {
      const match = historyHeaders.find(([name]) => name.toLowerCase() === 'authorization');
      authHeader = match?.[1];
    } else if (historyHeaders && isHeaderRecord(historyHeaders)) {
      authHeader = historyHeaders['Authorization'] ?? historyHeaders['authorization'];
    }
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
    let resolveHistory: ((response: Response) => void) | undefined;
    const deferred = new Promise<Response>((resolve) => {
      resolveHistory = resolve;
    });
    setupFetch({ history: deferred });

    const token = createTestToken();
    renderWithRouter(<ZooDetail zoo={zoo} refresh={0} onLogged={() => {}} />, {
      auth: { token, user: { id: userId, email: 'user@example.com' }, expiresIn: 3600 },
      route: '/en/zoos/test-zoo',
    });

    expect(await screen.findByText('Loading your visit history…')).toBeInTheDocument();

    if (resolveHistory) {
      resolveHistory(jsonResponse({ items: sightings, total: sightings.length, limit: 50, offset: 0 }));
    }
    await waitFor(() => {
      expect(screen.queryByText('Loading your visit history…')).not.toBeInTheDocument();
    });
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
    let historySignal: AbortSignal | undefined;
    const historyPromise = new Promise<Response>(() => {});
    fetchMock.mockImplementation((request: RequestInfo | URL, options: RequestInit = {}) => {
      const requestUrl =
        typeof request === 'string'
          ? request
          : request instanceof URL
            ? request.toString()
            : request.url;
      if (requestUrl.endsWith('/auth/refresh')) {
        return Promise.resolve(jsonResponse({ detail: 'unauthorized' }, 401));
      }
      if (requestUrl.endsWith(`/zoos/${zoo.slug}/animals`)) {
        return Promise.resolve(jsonResponse([{ id: animalId, name_en: 'Lion' }]));
      }
      if (requestUrl.endsWith(`/zoos/${zoo.slug}/visited`)) {
        return Promise.resolve(jsonResponse({ visited: true }));
      }
      if (requestUrl.endsWith(`/users/${userId}/animals/ids`)) {
        return Promise.resolve(jsonResponse([animalId]));
      }
      if (requestUrl.includes(`/zoos/${zoo.slug}/sightings`)) {
        historySignal = options.signal ?? undefined;
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

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringMatching(`${API}/zoos/${zoo.slug}/sightings`),
        expect.any(Object)
      );
    });

    unmount();
    if (!historySignal) {
      throw new Error('Expected history request to include an AbortSignal');
    }
    expect(historySignal.aborted).toBe(true);

    await act(async () => {
      await Promise.resolve();
    });
    expect(errorSpy).not.toHaveBeenCalled();
    errorSpy.mockRestore();
  });
});
