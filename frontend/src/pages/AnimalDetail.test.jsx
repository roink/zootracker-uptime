import React from 'react';
import '@testing-library/jest-dom';
import { screen } from '@testing-library/react';
import { describe, it, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { render } from '@testing-library/react';
import { routerFuture } from '../test-utils/router.jsx';

vi.mock('../hooks/useAuthFetch', () => ({ default: () => fetch }));
vi.mock('../components/Seo', () => ({ default: () => null }));

import AnimalDetailPage from './AnimalDetail.jsx';
import { API } from '../api';

describe('AnimalDetailPage', () => {
  const animal = {
    id: '1',
    name_en: 'Lion',
    name_de: 'Löwe',
    klasse_name_en: 'Mammals',
    klasse_name_de: 'Säugetiere',
    ordnung_name_en: 'Carnivorans',
    ordnung_name_de: 'Raubtiere',
    familie_name_en: 'Cats',
    familie_name_de: 'Katzen',
    zoos: [],
  };

  beforeEach(() => {
    vi.stubGlobal('navigator', { geolocation: { getCurrentPosition: (_s, e) => e() } });
  });

  it('shows classification names in English', async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve(animal) });
    render(
      <MemoryRouter initialEntries={['/en/animals/1']} future={routerFuture}>
        <Routes>
          <Route path="/:lang/animals/:id" element={<AnimalDetailPage />} />
        </Routes>
      </MemoryRouter>
    );
    await screen.findByText('Mammals');
    expect(screen.getByText('Carnivorans')).toBeInTheDocument();
    expect(screen.getByText('Cats')).toBeInTheDocument();
  });

  it('shows classification names in German', async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve(animal) });
    render(
      <MemoryRouter initialEntries={['/de/animals/1']} future={routerFuture}>
        <Routes>
          <Route path="/:lang/animals/:id" element={<AnimalDetailPage />} />
        </Routes>
      </MemoryRouter>
    );
    await screen.findByText('Säugetiere');
    expect(screen.getByText('Raubtiere')).toBeInTheDocument();
    expect(screen.getByText('Katzen')).toBeInTheDocument();
  });
});
