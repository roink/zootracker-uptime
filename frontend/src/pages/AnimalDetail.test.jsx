import React from 'react';
import '@testing-library/jest-dom';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, vi, beforeEach } from 'vitest';
import { Routes, Route } from 'react-router-dom';
import { renderWithRouter } from '../test-utils/router.jsx';
import { loadLocale } from '../i18n.js';

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
    class_id: 1,
    class_name_en: 'Mammals',
    class_name_de: 'Säugetiere',
    order_id: 2,
    order_name_en: 'Carnivorans',
    order_name_de: 'Raubtiere',
    family_id: 3,
    family_name_en: 'Cats',
    family_name_de: 'Katzen',
    zoos: [],
    parent: null,
    subspecies: [],
  };

  beforeEach(async () => {
    await loadLocale('en');
    vi.stubGlobal('navigator', { geolocation: { getCurrentPosition: (_s, e) => e() } });
    Object.defineProperty(global.window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
    mapMock.mockClear();
  });

  it('shows classification names in English', async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve(animal) });
    const user = userEvent.setup();
    const { container } = renderWithRouter(
      <Routes>
        <Route path="/:lang/animals/:slug" element={<AnimalDetailPage />} />
      </Routes>,
      { route: '/en/animals/lion' }
    );
    const taxonomyToggle = await screen.findByRole('button', {
      name: /Classification & relations/i,
    });
    await user.click(taxonomyToggle);
    await screen.findByText('Mammals');
    expect(screen.getByText('Carnivorans')).toBeInTheDocument();
    expect(screen.getByText('Cats')).toBeInTheDocument();
    expect(container.querySelector('dl')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Filter animals by class: Mammals' })
    ).toHaveAttribute('href', '/en/animals?class=1');
    expect(
      screen.getByRole('link', { name: 'Filter animals by order: Carnivorans' })
    ).toHaveAttribute('href', '/en/animals?class=1&order=2');
    expect(
      screen.getByRole('link', { name: 'Filter animals by family: Cats' })
    ).toHaveAttribute('href', '/en/animals?class=1&order=2&family=3');
  });

  it('shows classification names in German', async () => {
    await loadLocale('de');
    global.fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve(animal) });
    const user = userEvent.setup();
    renderWithRouter(
      <Routes>
        <Route path="/:lang/animals/:slug" element={<AnimalDetailPage />} />
      </Routes>,
      { route: '/de/animals/lion' }
    );
    const taxonomyToggle = await screen.findByRole('button', {
      name: /Klassifikation & Beziehungen/i,
    });
    await user.click(taxonomyToggle);
    await screen.findByText('Säugetiere');
    expect(screen.getByText('Raubtiere')).toBeInTheDocument();
    expect(screen.getByText('Katzen')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Tiere nach Klasse filtern: Säugetiere' })
    ).toHaveAttribute('href', '/de/animals?class=1');
    expect(
      screen.getByRole('link', { name: 'Tiere nach Ordnung filtern: Raubtiere' })
    ).toHaveAttribute('href', '/de/animals?class=1&order=2');
    expect(
      screen.getByRole('link', { name: 'Tiere nach Familie filtern: Katzen' })
    ).toHaveAttribute('href', '/de/animals?class=1&order=2&family=3');
  });

  it('renders the parent species link when available', async () => {
    const withParent = {
      ...animal,
      parent: {
        slug: 'panthera',
        name_en: 'Panthera',
        name_de: 'Panthera',
        scientific_name: 'Panthera',
      },
    };
    global.fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve(withParent) });

    const user = userEvent.setup();
    renderWithRouter(
      <Routes>
        <Route path="/:lang/animals/:slug" element={<AnimalDetailPage />} />
      </Routes>,
      { route: '/en/animals/lion' }
    );

    const taxonomyToggle = await screen.findByRole('button', {
      name: /Classification & relations/i,
    });
    await user.click(taxonomyToggle);

    const parentLink = await screen.findByRole('link', {
      name: 'View parent species Panthera',
    });
    expect(screen.getByText('Parent species')).toBeInTheDocument();
    expect(parentLink).toHaveAttribute('href', '/en/animals/panthera');
    expect(parentLink).toHaveTextContent('Panthera');
    expect(screen.getByText('Panthera', { selector: 'span.relation-scientific' })).toBeInTheDocument();
  });

  it('lists subspecies with localized names', async () => {
    await loadLocale('de');
    const withSubspecies = {
      ...animal,
      subspecies: [
        {
          slug: 'asiatischer-loewe',
          name_en: 'Asiatic Lion',
          name_de: 'Asiatischer Löwe',
          scientific_name: 'Panthera leo persica',
        },
      ],
    };
    global.fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve(withSubspecies) });

    const user = userEvent.setup();
    renderWithRouter(
      <Routes>
        <Route path="/:lang/animals/:slug" element={<AnimalDetailPage />} />
      </Routes>,
      { route: '/de/animals/lion' }
    );

    const taxonomyToggle = await screen.findByRole('button', {
      name: /Klassifikation & Beziehungen/i,
    });
    await user.click(taxonomyToggle);

    await screen.findByText('Unterarten');
    const subspeciesLink = screen.getByRole('link', {
      name: 'Unterart anzeigen: Asiatischer Löwe',
    });
    expect(subspeciesLink).toHaveAttribute('href', '/de/animals/asiatischer-loewe');
    expect(
      screen.getByText('Panthera leo persica', {
        selector: 'span.relation-scientific',
      })
    ).toBeInTheDocument();
  });

  it('opens the overview accordion by default and allows closing all sections', async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve(animal) });

    const user = userEvent.setup();
    renderWithRouter(
      <Routes>
        <Route path="/:lang/animals/:slug" element={<AnimalDetailPage />} />
      </Routes>,
      { route: '/en/animals/lion' }
    );

    const overviewToggle = await screen.findByRole('button', { name: /Overview/i });
    expect(overviewToggle).toHaveAttribute('aria-expanded', 'true');

    await user.click(overviewToggle);
    expect(overviewToggle).toHaveAttribute('aria-expanded', 'false');
  });

  it('only keeps one accordion section open on mobile when switching sections', async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve(animal) });

    const user = userEvent.setup();
    renderWithRouter(
      <Routes>
        <Route path="/:lang/animals/:slug" element={<AnimalDetailPage />} />
      </Routes>,
      { route: '/en/animals/lion' }
    );

    const overviewToggle = await screen.findByRole('button', { name: /Overview/i });
    const whereToggle = await screen.findByRole('button', { name: /Where to See/i });
    const sightingsToggle = await screen.findByRole('button', { name: /Your sightings/i });

    expect(overviewToggle).toHaveAttribute('aria-expanded', 'true');
    expect(whereToggle).toHaveAttribute('aria-expanded', 'false');
    expect(sightingsToggle).toHaveAttribute('aria-expanded', 'false');

    await user.click(whereToggle);
    expect(whereToggle).toHaveAttribute('aria-expanded', 'true');
    expect(overviewToggle).toHaveAttribute('aria-expanded', 'false');

    await user.click(sightingsToggle);
    expect(sightingsToggle).toHaveAttribute('aria-expanded', 'true');
    expect(whereToggle).toHaveAttribute('aria-expanded', 'false');
  });

  it('omits taxonomy links when identifiers are missing', async () => {
    const partialAnimal = {
      ...animal,
      order_id: null,
      family_id: null,
    };
    global.fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve(partialAnimal) });

    const user = userEvent.setup();
    renderWithRouter(
      <Routes>
        <Route path="/:lang/animals/:slug" element={<AnimalDetailPage />} />
      </Routes>,
      { route: '/en/animals/lion' }
    );

    const taxonomyToggle = await screen.findByRole('button', {
      name: /Classification & relations/i,
    });
    await user.click(taxonomyToggle);
    await screen.findByText('Mammals');
    expect(
      screen.getByRole('link', { name: 'Filter animals by class: Mammals' })
    ).toBeInTheDocument();
    expect(screen.getByText('Carnivorans')).toBeInTheDocument();
    expect(
      screen.queryByRole('link', {
        name: 'Filter animals by order: Carnivorans',
      })
    ).not.toBeInTheDocument();
    expect(screen.getByText('Cats')).toBeInTheDocument();
    expect(
      screen.queryByRole('link', {
        name: 'Filter animals by family: Cats',
      })
    ).not.toBeInTheDocument();
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
