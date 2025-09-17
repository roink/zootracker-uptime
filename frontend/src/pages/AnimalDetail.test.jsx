import React from 'react';
import '@testing-library/jest-dom';
import { screen } from '@testing-library/react';
import { describe, it, vi, beforeEach } from 'vitest';
import { Routes, Route } from 'react-router-dom';
import { routerFuture, renderWithRouter } from '../test-utils/router.jsx';

vi.mock('../hooks/useAuthFetch', () => ({ default: () => fetch }));
vi.mock('../components/Seo', () => ({ default: () => null }));

import AnimalDetailPage from './AnimalDetail.jsx';
import { API } from '../api';

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
  });

  it('shows classification names in English', async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve(animal) });
    const { container } = renderWithRouter(
      <Routes>
        <Route path="/:lang/animals/:slug" element={<AnimalDetailPage />} />
      </Routes>,
      { route: '/en/animals/lion', future: routerFuture }
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
      { route: '/de/animals/lion', future: routerFuture }
    );
    await screen.findByText('Säugetiere');
    expect(screen.getByText('Raubtiere')).toBeInTheDocument();
    expect(screen.getByText('Katzen')).toBeInTheDocument();
  });
});
