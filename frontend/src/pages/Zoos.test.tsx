import '@testing-library/jest-dom';
import { screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('maplibre-gl', () => import('../test-utils/maplibreMock'));
vi.mock('../hooks/useAuthFetch', () => ({
  default: () => global.fetch,
}));
vi.mock('../components/Seo', () => ({ default: () => null }));

import ZoosPage from './Zoos';
import { API } from '../api';
import { createTestToken, setStoredAuth, clearStoredAuth } from '../test-utils/auth';
import { renderWithRouter } from '../test-utils/router';

type FetchResult =
  | null
  | boolean
  | number
  | string
  | Record<string, unknown>
  | unknown[];

type FetchRouteResolver = (url: string) => FetchResult | Promise<FetchResult>;

type FetchRoutes = Record<string, FetchResult | FetchRouteResolver>;

function createFetchMock(routes: FetchRoutes) {
  return vi.fn(async (input: RequestInfo | URL) => {
    let url: string;
    if (typeof input === 'string') {
      url = input;
    } else if (input instanceof URL) {
      url = input.href;
    } else if (typeof Request !== 'undefined' && input instanceof Request) {
      url = input.url;
    } else {
      throw new Error('Unsupported request input');
    }

    const match = Object.entries(routes).find(([prefix]) => url.startsWith(prefix));
    if (!match) {
      throw new Error(`Unhandled request in test: ${url}`);
    }

    const [, handler] = match;
    const payload = typeof handler === 'function' ? await handler(url) : handler;
    return {
      ok: true,
      status: 200,
      json: () => Promise.resolve(payload),
    } as Response;
  });
}

function stubIntersectionObserver(): void {
  class MockObserver {
    callback: IntersectionObserverCallback;

    constructor(callback: IntersectionObserverCallback) {
      this.callback = callback;
    }

    observe(): void {
      // no-op for tests
    }

    disconnect(): void {
      // no-op for tests
    }

    unobserve(): void {
      // no-op for tests
    }

    takeRecords(): IntersectionObserverEntry[] {
      return [];
    }
  }

  vi.stubGlobal('IntersectionObserver', MockObserver);
}

describe('ZoosPage', () => {
  const originalFetch = global.fetch;
  let originalCreateObjectURL: typeof URL.createObjectURL | undefined;
  let originalRevokeObjectURL: typeof URL.revokeObjectURL | undefined;

  beforeEach(() => {
    stubIntersectionObserver();
    vi.stubGlobal('navigator', {
      geolocation: {
        getCurrentPosition: (_success: PositionCallback, error?: PositionErrorCallback | null) => {
          if (error) {
            error({} as GeolocationPositionError);
          }
        },
      },
    });
    if (typeof URL !== 'undefined') {
      const urlCtor = URL as typeof URL & {
        createObjectURL?: typeof URL.createObjectURL;
        revokeObjectURL?: typeof URL.revokeObjectURL;
      };
      originalCreateObjectURL = urlCtor.createObjectURL;
      originalRevokeObjectURL = urlCtor.revokeObjectURL;
      Object.defineProperty(urlCtor, 'createObjectURL', {
        configurable: true,
        writable: true,
        value: vi.fn(() => 'blob:mock'),
      });
      Object.defineProperty(urlCtor, 'revokeObjectURL', {
        configurable: true,
        writable: true,
        value: vi.fn(),
      });
    }
    localStorage.clear();
    clearStoredAuth();
  });

  afterEach(() => {
    clearStoredAuth();
    localStorage.clear();
    if (typeof URL !== 'undefined') {
      const urlCtor = URL as typeof URL & {
        createObjectURL?: typeof URL.createObjectURL;
        revokeObjectURL?: typeof URL.revokeObjectURL;
      };
      if (originalCreateObjectURL) {
        Object.defineProperty(urlCtor, 'createObjectURL', {
          configurable: true,
          writable: true,
          value: originalCreateObjectURL,
        });
      } else {
        Reflect.deleteProperty(urlCtor as unknown as Record<string, unknown>, 'createObjectURL');
      }
      if (originalRevokeObjectURL) {
        Object.defineProperty(urlCtor, 'revokeObjectURL', {
          configurable: true,
          writable: true,
          value: originalRevokeObjectURL,
        });
      } else {
        Reflect.deleteProperty(urlCtor as unknown as Record<string, unknown>, 'revokeObjectURL');
      }
      originalCreateObjectURL = undefined;
      originalRevokeObjectURL = undefined;
    }
    global.fetch = originalFetch;
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('renders fetched zoos and marks visited entries', async () => {
    const zooList = {
      id: '1',
      slug: 'berlin-zoo',
      name: 'Berlin Zoo',
      city: 'Berlin',
      country_name_en: 'Germany',
      distance_km: 2.3,
      is_favorite: false,
    };

    const fetchMock = createFetchMock({
      [`${API}/zoos/continents`]: [],
      [`${API}/zoos/map`]: [
        {
          id: '1',
          slug: 'berlin-zoo',
          name: 'Berlin Zoo',
          city: 'Berlin',
          latitude: 52.51,
          longitude: 13.4,
        },
      ],
      [`${API}/zoos?`]: {
        items: [zooList],
        total: 1,
        offset: 0,
        limit: 20,
      },
      [`${API}/visits/ids`]: ['1'],
      [`${API}/location/estimate`]: null,
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const token = createTestToken();
    setStoredAuth({ token, user: { id: 'user-1', email: 'user@example.com' } });

    renderWithRouter(<ZoosPage />);

    expect(await screen.findByText(/Berlin Zoo/)).toBeInTheDocument();
    const visitedBadge = await screen.findByText('Visited', { selector: 'span.badge' });
    expect(visitedBadge).toBeInTheDocument();

    await waitFor(() => {
      const invoked = fetchMock.mock.calls.some(([url]) =>
        typeof url === 'string' && url.startsWith(`${API}/zoos?`),
      );
      expect(invoked).toBe(true);
    });
  });

  it('prompts guests to log in to use visit filters', async () => {
    const fetchMock = createFetchMock({
      [`${API}/zoos/continents`]: [],
      [`${API}/zoos/map`]: [],
      [`${API}/zoos?`]: {
        items: [],
        total: 0,
        offset: 0,
        limit: 20,
      },
      [`${API}/location/estimate`]: null,
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    renderWithRouter(<ZoosPage />, { auth: null });

    const prompt = await screen.findByRole('status');
    expect(prompt).toHaveTextContent(/Log in/i);
    expect(prompt).toHaveTextContent(/create an account/i);
    expect(screen.queryByLabelText('Visited')).not.toBeInTheDocument();
  });

  it('filters zoos based on the visit query parameter', async () => {
    const listZoos = [
      {
        id: '1',
        slug: 'visited-zoo',
        name: 'Visited Zoo',
        city: 'Berlin',
        country_name_en: 'Germany',
        country_name_de: 'Deutschland',
      },
      {
        id: '2',
        slug: 'new-zoo',
        name: 'New Zoo',
        city: 'Boston',
        country_name_en: 'United States',
        country_name_de: 'USA',
      },
    ];
    const mapZoos = [
      {
        id: '1',
        slug: 'visited-zoo',
        name: 'Visited Zoo',
        city: 'Berlin',
        latitude: 52.5,
        longitude: 13.4,
      },
      {
        id: '2',
        slug: 'new-zoo',
        name: 'New Zoo',
        city: 'Boston',
        latitude: 42.3,
        longitude: -71.1,
      },
    ];

    const baseRoutes = {
      [`${API}/zoos/continents`]: [],
      [`${API}/zoos/map`]: mapZoos,
      [`${API}/zoos?`]: {
        items: listZoos,
        total: 2,
        offset: 0,
        limit: 20,
      },
      [`${API}/visits/ids`]: ['1'],
      [`${API}/location/estimate`]: null,
    } satisfies FetchRoutes;

    const token = createTestToken();
    const auth = { token, user: { id: 'user-1', email: 'user@example.com' } } as const;

    const renderWithAuth = (route: string, extraRoutes: FetchRoutes = {}) => {
      const fetchMock = createFetchMock({ ...baseRoutes, ...extraRoutes });
      global.fetch = fetchMock as unknown as typeof fetch;
      setStoredAuth(auth);
      return renderWithRouter(<ZoosPage />, { route, auth });
    };

    const visitedRender = renderWithAuth('/?visit=visited', {
      [`${API}/users/${auth.user.id}/zoos/visited`]: {
        items: [listZoos[0]],
        total: 1,
        offset: 0,
        limit: 20,
      },
      [`${API}/users/${auth.user.id}/zoos/visited/map`]: [mapZoos[0]],
    });
    expect(await screen.findByRole('link', { name: /Visited Zoo/ })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /New Zoo/ })).not.toBeInTheDocument();
    visitedRender.unmount();

    const notVisitedRender = renderWithAuth('/?visit=not', {
      [`${API}/users/${auth.user.id}/zoos/not-visited`]: {
        items: [listZoos[1]],
        total: 1,
        offset: 0,
        limit: 20,
      },
      [`${API}/users/${auth.user.id}/zoos/not-visited/map`]: [mapZoos[1]],
    });
    expect(await screen.findByRole('link', { name: /New Zoo/ })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Visited Zoo/ })).not.toBeInTheDocument();
    notVisitedRender.unmount();

    const allRender = renderWithAuth('/');
    expect(await screen.findByRole('link', { name: /Visited Zoo/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /New Zoo/ })).toBeInTheDocument();
    allRender.unmount();
  });

  it('shows a helper message when map results lack coordinates', async () => {
    const fetchMock = createFetchMock({
      [`${API}/zoos/continents`]: [],
      [`${API}/zoos/map`]: [
        {
          id: '2',
          name: 'Mystery Zoo',
          slug: 'mystery',
          latitude: null,
          longitude: null,
        },
      ],
      [`${API}/zoos?`]: {
        items: [],
        total: 0,
        offset: 0,
        limit: 20,
      },
      [`${API}/location/estimate`]: null,
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    renderWithRouter(<ZoosPage />, { route: '/?view=map' });

    const helper = await screen.findByText(
      'No map coordinates are available for these zoos yet. Switch back to the list view to explore them.',
    );
    expect(helper).toBeInTheDocument();
  });
});
