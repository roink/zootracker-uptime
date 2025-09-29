import React from 'react';
import '@testing-library/jest-dom';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, vi, beforeEach } from 'vitest';
import { Routes, Route } from 'react-router-dom';
import { renderWithRouter } from '../test-utils/router.jsx';

vi.mock('../hooks/useAuthFetch', () => ({ default: () => fetch }));
vi.mock('../components/Seo', () => ({ default: () => null }));
const { mapMock } = vi.hoisted(() => ({
  mapMock: vi.fn(() => <div data-testid="zoos-map" />),
}));
vi.mock('../components/ZoosMap.jsx', () => ({
  __esModule: true,
  default: mapMock,
}));

import AnimalDetailPage from './AnimalDetail.jsx';

describe('AnimalDetailPage', () => {
  const animal = {
    id: '1',
    slug: 'lion',
    name_en: 'Lion',
    name_de: 'Löwe',
    class_name_en: 'Mammals',
    class_name_de: 'Säugetiere',
    order_name_en: 'Carnivorans',
    order_name_de: 'Raubtiere',
    family_name_en: 'Cats',
    family_name_de: 'Katzen',
    zoos: [],
  };

  beforeEach(() => {
    vi.stubGlobal('navigator', { geolocation: { getCurrentPosition: (_s, e) => e() } });
    mapMock.mockClear();
  });

  it('shows classification names in English', async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve(animal) });
    const { container } = renderWithRouter(
      <Routes>
        <Route path="/:lang/animals/:slug" element={<AnimalDetailPage />} />
      </Routes>,
      { route: '/en/animals/lion' }
    );
    await screen.findByText('Mammals');
    expect(screen.getByText('Carnivorans')).toBeInTheDocument();
    expect(screen.getByText('Cats')).toBeInTheDocument();
    expect(container.querySelector('dl')).toBeInTheDocument();
  });

  it('shows classification names in German', async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve(animal) });
    renderWithRouter(
      <Routes>
        <Route path="/:lang/animals/:slug" element={<AnimalDetailPage />} />
      </Routes>,
      { route: '/de/animals/lion' }
    );
    await screen.findByText('Säugetiere');
    expect(screen.getByText('Raubtiere')).toBeInTheDocument();
    expect(screen.getByText('Katzen')).toBeInTheDocument();
  });

  it('renders the zoo map when map view is selected', async () => {
    const fetchResponse = {
      ...animal,
      zoos: [
        {
          id: 'z1',
          slug: 'central-zoo',
          name: 'Central Zoo',
          city: 'Metropolis',
          latitude: 10,
          longitude: 20,
        },
      ],
    };
    global.fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve(fetchResponse) });

    const user = userEvent.setup();
    renderWithRouter(
      <Routes>
        <Route path="/:lang/animals/:slug" element={<AnimalDetailPage />} />
      </Routes>,
      { route: '/en/animals/lion' }
    );

    await screen.findByText('Mammals');
    expect(screen.queryByTestId('zoos-map')).not.toBeInTheDocument();

    const mapToggle = screen.getByRole('radio', { name: 'Map' });
    await user.click(mapToggle);

    expect(await screen.findByTestId('zoos-map')).toBeInTheDocument();
  });

  it('restores the map view from navigation state', async () => {
    const fetchResponse = {
      ...animal,
      zoos: [
        {
          id: 'z1',
          slug: 'central-zoo',
          name: 'Central Zoo',
          city: 'Metropolis',
          latitude: 10,
          longitude: 20,
        },
      ],
    };
    global.fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve(fetchResponse) });

    const savedView = {
      center: [20.123456, 10.654321],
      zoom: 7.5,
      bearing: 15.25,
      pitch: 10.5,
    };

    renderWithRouter(
      <Routes>
        <Route path="/:lang/animals/:slug" element={<AnimalDetailPage />} />
      </Routes>,
      {
        initialEntries: [
          {
            pathname: '/en/animals/lion',
            state: { animalViewMode: 'map', animalMapView: savedView },
          },
        ],
      }
    );

    await screen.findByText('Mammals');

    const mapRadio = screen.getByRole('radio', { name: 'Map' });
    expect(mapRadio).toBeChecked();

    expect(mapMock).toHaveBeenCalled();
    const mapProps = mapMock.mock.calls[mapMock.mock.calls.length - 1][0];
    expect(mapProps.initialView).toMatchObject({
      center: savedView.center,
      zoom: savedView.zoom,
      bearing: savedView.bearing,
      pitch: savedView.pitch,
    });
    expect(mapProps.resizeToken).toBe(1);
  });
});
