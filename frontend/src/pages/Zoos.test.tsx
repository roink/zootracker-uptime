// @ts-nocheck
import React from 'react';
import '@testing-library/jest-dom';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { useLocation } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { URL as NodeURL } from 'node:url';


vi.mock('maplibre-gl', () => import('../test-utils/maplibreMock'));
vi.mock('../hooks/useAuthFetch', () => ({ default: () => fetch }));
vi.mock('../components/Seo', () => ({ default: () => null }));

import ZoosPage from './Zoos';
import { API } from '../api';
import { createTestToken, setStoredAuth, clearStoredAuth } from '../test-utils/auth';
import { renderWithRouter } from '../test-utils/router';

const originalFetch = global.fetch;
const TEST_BASE_URL = 'http://test/';

const paginated = (items) => ({
  items,
  total: items.length,
  limit: 20,
  offset: 0,
});

const jsonResponse = (value) =>
  Promise.resolve({ ok: true, json: () => Promise.resolve(value) });

const normalizeHref = (value) => new NodeURL(value, TEST_BASE_URL).href;

const resolveFetchUrl = (input) => {
  if (typeof input === 'string') {
    return new NodeURL(input, TEST_BASE_URL);
  }
  if (input && typeof input === 'object') {
    if ('url' in input && input.url) {
      return new NodeURL(input.url, TEST_BASE_URL);
    }
    if ('href' in input && input.href) {
      return new NodeURL(input.href, TEST_BASE_URL);
    }
  }
  return new NodeURL(String(input), TEST_BASE_URL);
};

const createZooFetchMock = ({
  listZoos = [],
  mapZoos = [],
  visitedIds = [],
  userId = 'user-1',
  extra = {},
} = {}) => {
  const visitedIdSet = new Set(visitedIds.map((value) => String(value)));
  const extraHandlers = Object.entries(extra).map(([prefix, handler]) => [
    normalizeHref(prefix),
    handler,
  ]);
  const continentsPrefix = normalizeHref(`${API}/zoos/continents`);
  const countriesPrefix = normalizeHref(`${API}/zoos/countries`);
  const visitsIdsPrefix = normalizeHref(`${API}/visits/ids`);
  const visitedMapPrefix = normalizeHref(`${API}/users/${userId}/zoos/visited/map`);
  const notVisitedMapPrefix = normalizeHref(
    `${API}/users/${userId}/zoos/not-visited/map`
  );
  const mapPrefix = normalizeHref(`${API}/zoos/map`);
  const locationEstimatePrefix = normalizeHref(`${API}/location/estimate`);
  const visitedListPrefix = normalizeHref(`${API}/users/${userId}/zoos/visited`);
  const notVisitedListPrefix = normalizeHref(
    `${API}/users/${userId}/zoos/not-visited`
  );
  const zoosQueryPrefix = normalizeHref(`${API}/zoos?`);
  const zoosBase = normalizeHref(`${API}/zoos`);

  return vi.fn((input) => {
    const url = resolveFetchUrl(input);
    const href = url.href;

    for (const [prefix, handler] of extraHandlers) {
      if (href.startsWith(prefix)) {
        return handler(href);
      }
    }

    if (href.startsWith(continentsPrefix)) return jsonResponse([]);
    if (href.startsWith(countriesPrefix)) return jsonResponse([]);
    if (href.startsWith(visitsIdsPrefix)) return jsonResponse(visitedIds);
    if (href.startsWith(visitedMapPrefix)) {
      return jsonResponse(
        mapZoos.filter((zoo) => visitedIdSet.has(String(zoo.id)))
      );
    }
    if (href.startsWith(notVisitedMapPrefix)) {
      return jsonResponse(
        mapZoos.filter((zoo) => !visitedIdSet.has(String(zoo.id)))
      );
    }
    if (href.startsWith(mapPrefix)) return jsonResponse(mapZoos);
    if (href.startsWith(locationEstimatePrefix)) return jsonResponse(null);
    if (href.startsWith(visitedListPrefix) && !href.startsWith(visitedMapPrefix)) {
      return jsonResponse(
        paginated(listZoos.filter((zoo) => visitedIdSet.has(String(zoo.id))))
      );
    }
    if (
      href.startsWith(notVisitedListPrefix) &&
      !href.startsWith(notVisitedMapPrefix)
    ) {
      return jsonResponse(
        paginated(listZoos.filter((zoo) => !visitedIdSet.has(String(zoo.id))))
      );
    }
    if (href.startsWith(zoosQueryPrefix) || href === zoosBase) {
      const visitFilter = url.searchParams.get('visit');
      let items = listZoos;
      if (visitFilter === 'visited') {
        items = listZoos.filter((zoo) => visitedIdSet.has(String(zoo.id)));
      } else if (visitFilter === 'not_visited') {
        items = listZoos.filter((zoo) => !visitedIdSet.has(String(zoo.id)));
      }
      return jsonResponse(paginated(items));
    }

    // eslint-disable-next-line no-console
    console.error('UNMOCKED FETCH:', href);
    throw new Error(`Unmocked fetch in test: ${href}`);
  });
};

describe('ZoosPage', () => {
  let consoleWarnSpy;

  beforeEach(() => {
    vi.stubGlobal('navigator', {
      geolocation: { getCurrentPosition: (_s, e) => e() },
    });
    const existingUrl = typeof URL !== 'undefined' ? URL : undefined;
    vi.stubGlobal('URL', {
      ...(existingUrl || {}),
      createObjectURL: vi.fn(() => 'blob:mock'),
      revokeObjectURL: vi.fn(),
    });
    const token = createTestToken();
    setStoredAuth({ token, user: { id: 'user-1', email: 'user@example.com' } });
    consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    expect(consoleWarnSpy).not.toHaveBeenCalled();
    consoleWarnSpy.mockRestore();
    clearStoredAuth();
    vi.unstubAllGlobals();
    if (originalFetch) {
      global.fetch = originalFetch;
    } else {
      delete global.fetch;
    }
  });

  it('loads visited zoo IDs and marks visited zoos', async () => {
    const zoos = [
      {
        id: '1',
        slug: 'a-zoo',
        name: 'A Zoo',
        city: '',
        latitude: 10.123,
        longitude: 20.456,
        country_name_en: 'Germany',
        country_name_de: 'Deutschland',
      },
    ];
    const listZoos = zoos.map(({ latitude, longitude, ...rest }) => rest);
    const mapZoos = zoos.map(({ id, slug, name, city, latitude, longitude }) => ({
      id,
      slug,
      name,
      city,
      latitude,
      longitude,
    }));
    const visited = ['1'];
    const fetchMock = createZooFetchMock({
      listZoos,
      mapZoos,
      visitedIds: visited,
    });
    global.fetch = fetchMock;

    renderWithRouter(<ZoosPage />);

    await waitFor(() => { expect(fetchMock).toHaveBeenCalled(); });
    const badges = await screen.findAllByText('Visited', { selector: 'span' });
    expect(badges[0]).toBeInTheDocument();
    expect(await screen.findByText(/^Germany$/)).toBeInTheDocument();
  });

  it('shows favorite badges even when the favorites filter is off', async () => {
    const listZoos = [
      {
        id: 'fav-1',
        slug: 'favorite-zoo',
        name: 'Favorite Zoo',
        city: 'Metropolis',
        country_name_en: 'Germany',
        country_name_de: 'Deutschland',
        distance_km: 3.2,
        is_favorite: true,
      },
    ];
    const mapZoos = [
      {
        id: 'fav-1',
        slug: 'favorite-zoo',
        name: 'Favorite Zoo',
        city: 'Metropolis',
        latitude: 48.1,
        longitude: 11.6,
      },
    ];
    const fetchMock = createZooFetchMock({ listZoos, mapZoos });
    global.fetch = fetchMock;

    renderWithRouter(<ZoosPage />);

    expect(await screen.findByText(/Favorite Zoo/)).toBeInTheDocument();
    expect(screen.getByLabelText('Favorite')).toBeInTheDocument();
  });

  it('provides separate datasets for visited and not visited zoo requests', async () => {
    const listZoos = [
      {
        id: '1',
        slug: 'visited-zoo',
        name: 'Visited Zoo',
        country_name_en: 'Germany',
        country_name_de: 'Deutschland',
      },
      {
        id: '2',
        slug: 'new-zoo',
        name: 'New Zoo',
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
    const fetchMock = createZooFetchMock({
      listZoos,
      mapZoos,
      visitedIds: ['1'],
    });

    const visitedList = await fetchMock(
      `${API}/users/user-1/zoos/visited?limit=20&offset=0`
    ).then((response) => response.json());
    const notVisitedList = await fetchMock(
      `${API}/users/user-1/zoos/not-visited?limit=20&offset=0`
    ).then((response) => response.json());
    const allZoos = await fetchMock(`${API}/zoos?limit=20&offset=0`).then((response) =>
      response.json()
    );
    const visitedQuery = await fetchMock(`${API}/zoos?visit=visited`).then((response) =>
      response.json()
    );
    const notVisitedQuery = await fetchMock(`${API}/zoos?visit=not_visited`).then(
      (response) => response.json()
    );
    const visitedMap = await fetchMock(
      `${API}/users/user-1/zoos/visited/map?limit=20`
    ).then((response) => response.json());
    const notVisitedMap = await fetchMock(
      `${API}/users/user-1/zoos/not-visited/map?limit=20`
    ).then((response) => response.json());

    expect(visitedList.items.map((zoo) => zoo.id)).toEqual(['1']);
    expect(notVisitedList.items.map((zoo) => zoo.id)).toEqual(['2']);
    expect(allZoos.items.map((zoo) => zoo.id)).toEqual(['1', '2']);
    expect(visitedQuery.items.map((zoo) => zoo.id)).toEqual(['1']);
    expect(notVisitedQuery.items.map((zoo) => zoo.id)).toEqual(['2']);
    expect(visitedMap.map((zoo) => zoo.id)).toEqual(['1']);
    expect(notVisitedMap.map((zoo) => zoo.id)).toEqual(['2']);
  });

  it('prompts anonymous visitors to sign in for visit filters', async () => {
    clearStoredAuth();
    const fetchMock = createZooFetchMock({
      extra: {
        [`${API}/auth/refresh`]: () =>
          Promise.resolve({ ok: false, status: 401 }),
      },
    });
    global.fetch = fetchMock;

    renderWithRouter(<ZoosPage />, { auth: null });

    const region = await screen.findByRole('status');
    expect(region).toHaveTextContent(/Log in/i);
    expect(region).toHaveTextContent(/create an account/i);
    expect(screen.getByRole('link', { name: /Log in/i })).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /create an account/i })
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/Visited/i)).toBeNull();
  });

  it('reads visit filter from URL', async () => {
    const zoos = [
      {
        id: '1',
        slug: 'visited-zoo',
        name: 'Visited Zoo',
        city: '',
        latitude: 50.0,
        longitude: 7.0,
        country_name_en: 'Germany',
        country_name_de: 'Deutschland',
      },
      {
        id: '2',
        slug: 'new-zoo',
        name: 'New Zoo',
        city: '',
        latitude: 51.0,
        longitude: 8.0,
        country_name_en: 'United States',
        country_name_de: 'USA',
      },
    ];
    const listZoos = zoos.map(({ latitude, longitude, ...rest }) => rest);
    const mapZoos = zoos.map(({ id, slug, name, city, latitude, longitude }) => ({
      id,
      slug,
      name,
      city,
      latitude,
      longitude,
    }));
    const visited = ['1'];
    const fetchMock = createZooFetchMock({
      listZoos,
      mapZoos,
      visitedIds: visited,
    });
    global.fetch = fetchMock;

    renderWithRouter(<ZoosPage />, { route: '/?visit=visited' });

    await screen.findByText('Visited Zoo');
    await waitFor(() => {
      expect(screen.getByLabelText('Visited')).toBeChecked();
    });
  });

  it('syncs search query with URL params', async () => {
    const zoos = [
      {
        id: '1',
        name: 'A Zoo',
        city: '',
        latitude: 1.5,
        longitude: 2.5,
        country_name_en: 'Germany',
        country_name_de: 'Deutschland',
      },
    ];
    const listZoos = zoos.map(({ latitude, longitude, ...rest }) => rest);
    const mapZoos = zoos.map(({ id, name, city, latitude, longitude }) => ({
      id,
      slug: id,
      name,
      city,
      latitude,
      longitude,
    }));
    const fetchMock = createZooFetchMock({
      listZoos,
      mapZoos,
    });
    global.fetch = fetchMock;

    let loc;
    function LocWatcher() {
      loc = useLocation();
      return null;
    }

    renderWithRouter(
      <>
        <LocWatcher />
        <ZoosPage token="t" />
      </>,
      { route: '/?q=start' }
    );

    const input = screen.getByPlaceholderText('Search');
    expect(input).toHaveValue('start');

    fireEvent.change(input, { target: { value: 'new' } });
    await waitFor(() => {
      expect(loc.search).toContain('q=new');
    });
  });

  it('uses region and search params from URL when loading', async () => {
    const fetchMock = createZooFetchMock();
    global.fetch = fetchMock;

    renderWithRouter(<ZoosPage token="t" />, {
      route: '/?continent=1&country=2&q=bear',
    });

    await waitFor(() => {
      const zooCall = fetchMock.mock.calls.find(([u]) =>
        u.startsWith(`${API}/zoos?`)
      );
      expect(zooCall[0]).toContain('continent_id=1');
      expect(zooCall[0]).toContain('country_id=2');
      expect(zooCall[0]).toContain('q=bear');
    });
  });

  it('fetches location estimate once and includes coordinates in zoo search', async () => {
    const zoos = [] as any[];
    const fetchMock = createZooFetchMock({
      extra: {
        [`${API}/location/estimate`]: () =>
          jsonResponse({ latitude: 50.5, longitude: 8.6 }),
      },
    });
    global.fetch = fetchMock;

    renderWithRouter(<ZoosPage />, { route: '/?view=map' });

    await waitFor(() => {
      const estimateCalls = fetchMock.mock.calls.filter(([u]) =>
        u.startsWith(`${API}/location/estimate`)
      );
      expect(estimateCalls).toHaveLength(1);
    });

    await waitFor(() => {
      const zooCalls = fetchMock.mock.calls.filter(([u]) =>
        u.startsWith(`${API}/zoos?`)
      );
      expect(zooCalls.length).toBeGreaterThan(0);
      const lastCall = zooCalls[zooCalls.length - 1];
      expect(lastCall[0]).toContain('latitude=50.5');
      expect(lastCall[0]).toContain('longitude=8.6');
    });
  });

  it('shows a helper message when map view has no coordinates', async () => {
    const zoos = [
      {
        id: '1',
        slug: 'no-map-zoo',
        name: 'No Map Zoo',
        city: '',
        latitude: null,
        longitude: null,
      },
    ];
    const listZoos = zoos.map(({ latitude, longitude, ...rest }) => rest);
    const fetchMock = createZooFetchMock({
      listZoos,
      mapZoos: zoos,
      extra: {
        [`${API}/location/estimate`]: () =>
          jsonResponse({ latitude: 40.1, longitude: -73.9 }),
      },
    });
    global.fetch = fetchMock;

    renderWithRouter(<ZoosPage />, { route: '/?view=map' });

    const message = await screen.findByText(
      'No map coordinates are available for these zoos yet. Switch back to the list view to explore them.'
    );
    expect(message).toBeInTheDocument();
  });

  it('persists the map camera when toggling between map and list views', async () => {
    const fetchMock = createZooFetchMock();
    global.fetch = fetchMock;

    const initialCamera = {
      center: [8.6, 50.1],
      zoom: 7.5,
      bearing: 12,
      pitch: 15,
    };

    let loc;
    function LocWatcher() {
      loc = useLocation();
      return null;
    }

    renderWithRouter(
      <>
        <LocWatcher />
        <ZoosPage />
      </>,
      {
        route: {
          pathname: '/',
          search: '?view=map',
          state: { mapView: initialCamera },
        },
      }
    );

    await waitFor(() => { expect(screen.getByLabelText('Map')).toBeChecked(); });
    expect(loc.state?.mapView).toEqual(initialCamera);

    fireEvent.click(screen.getByLabelText('List'));
    await waitFor(() => { expect(screen.getByLabelText('List')).toBeChecked(); });
    await waitFor(() => { expect(loc.state?.mapView).toEqual(initialCamera); });

    fireEvent.click(screen.getByLabelText('Map'));
    await waitFor(() => { expect(screen.getByLabelText('Map')).toBeChecked(); });
    await waitFor(() => { expect(loc.state?.mapView).toEqual(initialCamera); });
  });
});
