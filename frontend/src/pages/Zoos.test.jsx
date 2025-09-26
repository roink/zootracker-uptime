import React from 'react';
import '@testing-library/jest-dom';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { useLocation } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithRouter } from '../test-utils/router.jsx';

vi.mock('../hooks/useAuthFetch', () => ({ default: () => fetch }));
vi.mock('../components/Seo', () => ({ default: () => null }));

import ZoosPage from './Zoos.jsx';
import { API } from '../api';
import { createTestToken, setStoredAuth } from '../test-utils/auth.js';

describe('ZoosPage', () => {
  beforeEach(() => {
    vi.stubGlobal('navigator', {
      geolocation: { getCurrentPosition: (_s, e) => e() },
    });
    const token = createTestToken();
    setStoredAuth({ token, user: { id: 'user-1', email: 'user@example.com' } });
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
    const visited = ['1'];
    const fetchMock = vi.fn((url) => {
      if (url.startsWith(`${API}/zoos/continents`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      if (url.startsWith(`${API}/zoos`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve(zoos) });
      if (url.startsWith(`${API}/visits/ids`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve(visited) });
      if (url.startsWith(`${API}/zoos/countries`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    });
    global.fetch = fetchMock;

    renderWithRouter(<ZoosPage />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const badges = await screen.findAllByText('Visited', { selector: 'span' });
    expect(badges[0]).toBeInTheDocument();
    expect(await screen.findByText(/^Germany$/)).toBeInTheDocument();
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
    const visited = ['1'];
    const fetchMock = vi.fn((url) => {
      if (url.startsWith(`${API}/zoos/continents`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      if (url.startsWith(`${API}/zoos`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve(zoos) });
      if (url.startsWith(`${API}/visits/ids`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve(visited) });
      if (url.startsWith(`${API}/zoos/countries`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
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
    const visited = ['1'];
    const fetchMock = vi.fn((url) => {
      if (url.startsWith(`${API}/zoos/continents`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      if (url.startsWith(`${API}/zoos`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve(zoos) });
      if (url.startsWith(`${API}/visits/ids`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve(visited) });
      if (url.startsWith(`${API}/zoos/countries`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
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
    const fetchMock = vi.fn((url) => {
      if (url.startsWith(`${API}/zoos/continents`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      if (url.startsWith(`${API}/zoos`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve(zoos) });
      if (url.startsWith(`${API}/visits/ids`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      if (url.startsWith(`${API}/zoos/countries`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
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
    const fetchMock = vi.fn((url) => {
      if (url.startsWith(`${API}/zoos/continents`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      if (url.startsWith(`${API}/zoos/countries`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      if (url.startsWith(`${API}/visits/ids`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      if (url.startsWith(`${API}/zoos?`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    });
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
    const zoos = [];
    const fetchMock = vi.fn((url) => {
      if (url.startsWith(`${API}/zoos/continents`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      if (url.startsWith(`${API}/zoos/countries`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      if (url.startsWith(`${API}/visits/ids`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      if (url.startsWith(`${API}/location/estimate`))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ latitude: 50.5, longitude: 8.6 }),
        });
      if (url.startsWith(`${API}/zoos`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve(zoos) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
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
      const zooCall = fetchMock.mock.calls.find(([u]) =>
        u.startsWith(`${API}/zoos?`)
      );
      expect(zooCall).toBeDefined();
      expect(zooCall[0]).toContain('latitude=50.5');
      expect(zooCall[0]).toContain('longitude=8.6');
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
    const fetchMock = vi.fn((url) => {
      if (url.startsWith(`${API}/zoos/continents`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      if (url.startsWith(`${API}/zoos/countries`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      if (url.startsWith(`${API}/visits/ids`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      if (url.startsWith(`${API}/location/estimate`))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ latitude: 40.1, longitude: -73.9 }),
        });
      if (url.startsWith(`${API}/zoos`))
        return Promise.resolve({ ok: true, json: () => Promise.resolve(zoos) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    });
    global.fetch = fetchMock;

    renderWithRouter(<ZoosPage />, { route: '/?view=map' });

    const message = await screen.findByText(
      'No map coordinates are available for these zoos yet. Switch back to the list view to explore them.'
    );
    expect(message).toBeInTheDocument();
  });

  it('persists the map camera when toggling between map and list views', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
    );
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
