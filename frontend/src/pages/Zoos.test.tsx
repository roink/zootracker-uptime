// @ts-nocheck
import React from 'react';
import '@testing-library/jest-dom';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { useLocation } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithRouter } from '../test-utils/router';

vi.mock('maplibre-gl', () => import('../test-utils/maplibreMock'));
vi.mock('../hooks/useAuthFetch', () => ({ default: () => fetch }));
vi.mock('../components/Seo', () => ({ default: () => null }));

import ZoosPage from './Zoos';
import { API } from '../api';
import { createTestToken, setStoredAuth, clearStoredAuth } from '../test-utils/auth';

const originalFetch = global.fetch;

const paginated = (items) => ({
  items,
  total: items.length,
  limit: 20,
  offset: 0,
});

const jsonResponse = (value) =>
  Promise.resolve({ ok: true, json: () => Promise.resolve(value) });

const createZooFetchMock = ({
  listZoos = [],
  mapZoos = [],
  visitedIds = [],
  userId = 'user-1',
  extra = {},
} = {}) =>
  vi.fn((url) => {
    for (const [prefix, handler] of Object.entries(extra)) {
      if (url.startsWith(prefix)) {
        return handler(url);
      }
    }
    if (url.startsWith(`${API}/zoos/continents`)) return jsonResponse([]);
    if (url.startsWith(`${API}/zoos/countries`)) return jsonResponse([]);
    if (url.startsWith(`${API}/visits/ids`)) return jsonResponse(visitedIds);
    if (url.startsWith(`${API}/users/${userId}/zoos/visited/map`))
      return jsonResponse(
        mapZoos.filter((z) => visitedIds.includes(String(z.id)))
      );
    if (url.startsWith(`${API}/users/${userId}/zoos/not-visited/map`))
      return jsonResponse(
        mapZoos.filter((z) => !visitedIds.includes(String(z.id)))
      );
    if (url.startsWith(`${API}/zoos/map`)) return jsonResponse(mapZoos);
    if (url.startsWith(`${API}/users/${userId}/zoos/visited`))
      return jsonResponse(
        paginated(listZoos.filter((z) => visitedIds.includes(String(z.id))))
      );
    if (url.startsWith(`${API}/users/${userId}/zoos/not-visited`))
      return jsonResponse(
        paginated(listZoos.filter((z) => !visitedIds.includes(String(z.id))))
      );
    if (url.startsWith(`${API}/zoos?`)) return jsonResponse(paginated(listZoos));
    return jsonResponse([]);
  });

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

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
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

  it('filters zoos by visit status', async () => {
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

    renderWithRouter(<ZoosPage />);

    // ensure items are rendered
    await screen.findByText('Visited Zoo');
    await screen.findByText('New Zoo');
    await waitFor(() =>
      expect(screen.getByLabelText('Visited')).not.toBeDisabled()
    );

    // show only visited zoos
    fireEvent.click(screen.getByLabelText('Visited'));
    await waitFor(() => {
      expect(screen.getByText('Visited Zoo')).toBeInTheDocument();
      expect(screen.queryByText('New Zoo')).toBeNull();
    });

    // show only not visited zoos
    fireEvent.click(screen.getByLabelText('Not visited'));
    await waitFor(() => {
      expect(screen.getByText('New Zoo')).toBeInTheDocument();
      expect(screen.queryByText('Visited Zoo')).toBeNull();
    });

    // back to all zoos
    fireEvent.click(screen.getByLabelText('All'));
    await waitFor(() => {
      expect(screen.getByText('Visited Zoo')).toBeInTheDocument();
      expect(screen.getByText('New Zoo')).toBeInTheDocument();
    });
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
    await waitFor(() =>
      expect(screen.getByLabelText('Visited')).toBeChecked()
    );
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

    await waitFor(() => expect(screen.getByLabelText('Map')).toBeChecked());
    expect(loc.state?.mapView).toEqual(initialCamera);

    fireEvent.click(screen.getByLabelText('List'));
    await waitFor(() => expect(screen.getByLabelText('List')).toBeChecked());
    await waitFor(() => expect(loc.state?.mapView).toEqual(initialCamera));

    fireEvent.click(screen.getByLabelText('Map'));
    await waitFor(() => expect(screen.getByLabelText('Map')).toBeChecked());
    await waitFor(() => expect(loc.state?.mapView).toEqual(initialCamera));
  });
});
