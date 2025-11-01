// @ts-nocheck
import '@testing-library/jest-dom';
import { screen, waitFor } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API } from '../api';
import { loadLocale } from '../i18n';
import ZooDetailPage from './ZooDetail';
import { renderWithRouter } from '../test-utils/router';

const { seoSpy } = vi.hoisted(() => ({
  seoSpy: vi.fn(),
}));
const { zooDetailSpy } = vi.hoisted(() => ({
  zooDetailSpy: vi.fn(),
}));

vi.mock('../components/Seo', () => ({
  __esModule: true,
  default: (props) => {
    seoSpy(props);
    return null;
  },
}));

vi.mock('../components/ZooDetail', () => ({
  __esModule: true,
  default: (props) => {
    zooDetailSpy(props);
    return <div data-testid="zoo-detail" />;
  },
}));

async function prepareLocale() {
  await loadLocale('en');
}

describe('ZooDetailPage', () => {
  const originalFetch = global.fetch;

  beforeEach(async () => {
    await prepareLocale();
    seoSpy.mockClear();
    zooDetailSpy.mockClear();
  });

  afterEach(() => {
    if (originalFetch) {
      global.fetch = originalFetch;
    } else {
      delete global.fetch;
    }
  });

  it('provides sanitized SEO metadata while loading', async () => {
    global.fetch = vi.fn(() => new Promise(() => {}));

    renderWithRouter(
      <Routes>
        <Route path="/:lang/zoos/:slug" element={<ZooDetailPage />} />
      </Routes>,
      { route: '/en/zoos/berlin-zoo' }
    );

    expect(await screen.findByText('Loading...')).toBeInTheDocument();

    await waitFor(() => { expect(seoSpy).toHaveBeenCalled(); });
    expect(global.fetch).toHaveBeenCalledWith(
      `${API}/zoos/berlin-zoo`,
      expect.objectContaining({ signal: expect.any(Object) })
    );

    const lastCall = seoSpy.mock.calls.at(-1)[0];
    expect(lastCall.title).toBe('berlin-zoo');
    expect(lastCall.description).toBe('Learn about berlin-zoo and plan your visit.');
    expect(lastCall.canonical).toBe('/en/zoos/berlin-zoo');
    expect(lastCall.jsonLd).toBeUndefined();
    expect(zooDetailSpy).not.toHaveBeenCalled();
  });

  it('sanitizes meta description and emits structured data after loading', async () => {
    const response = {
      id: 'zoo-1',
      slug: 'berlin-zoo',
      name: 'Berlin Zoo',
      city: 'Berlin',
      seo_description_en: '  <b>Plan a visit to Berlin Zoo</b> today!  ',
      description_en: null,
      seo_description_de: null,
      description_de: null,
      latitude: 52.507,
      longitude: 13.338,
      country: 'Germany',
    };
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(response),
      })
    );

    renderWithRouter(
      <Routes>
        <Route path="/:lang/zoos/:slug" element={<ZooDetailPage />} />
      </Routes>,
      { route: '/en/zoos/berlin-zoo' }
    );

    await waitFor(() => { expect(zooDetailSpy).toHaveBeenCalled(); });

    const lastCall = seoSpy.mock.calls.at(-1)[0];
    expect(lastCall.description).toBe('Plan a visit to Berlin Zoo today!');
    expect(lastCall.jsonLd).toEqual(
      expect.objectContaining({
        '@type': 'Zoo',
        name: 'Berlin: Berlin Zoo',
        geo: {
          '@type': 'GeoCoordinates',
          latitude: 52.507,
          longitude: 13.338,
        },
      })
    );
    expect(lastCall.canonical).toBe('/en/zoos/berlin-zoo');
    expect(zooDetailSpy.mock.calls.at(-1)[0].displayName).toBe('Berlin: Berlin Zoo');
  });

  it('aborts in-flight fetches when unmounted', async () => {
    const abortSpy = vi.spyOn(AbortController.prototype, 'abort');
    global.fetch = vi.fn(() => new Promise(() => {}));

    const { unmount } = renderWithRouter(
      <Routes>
        <Route path="/:lang/zoos/:slug" element={<ZooDetailPage />} />
      </Routes>,
      { route: '/en/zoos/berlin-zoo' }
    );

    expect(await screen.findByText('Loading...')).toBeInTheDocument();
    unmount();
    expect(abortSpy).toHaveBeenCalledTimes(1);
    abortSpy.mockRestore();
  });
});
