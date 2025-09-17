import { screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderWithRouter } from '../test-utils/router.jsx';
import ZooDetail from './ZooDetail';
import { API } from '../api';
import { createTestToken, setStoredAuth } from '../test-utils/auth.js';
vi.mock('./LazyMap', () => ({ default: () => <div data-testid="map" /> }));

describe('ZooDetail component', () => {
  const zoo = { id: 'z1', slug: 'test-zoo', name: 'Test Zoo' };
  const userId = 'u1';
  const animalId = 'a1';

  beforeEach(() => {
    const token = createTestToken();
    setStoredAuth({ token, user: { id: userId, email: 'user@example.com' } });
    global.fetch = vi.fn((url) => {
      if (url.endsWith(`/zoos/${zoo.slug}/animals`)) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([{ id: animalId, name_en: 'Lion' }]),
        });
      }
      if (url.endsWith(`/zoos/${zoo.slug}/visited`)) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ visited: true }),
        });
      }
      if (url.endsWith(`/users/${userId}/animals/ids`)) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([animalId]),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows visit status and seen marker', async () => {
    renderWithRouter(<ZooDetail zoo={zoo} refresh={0} onLogged={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('Visited? ☑️ Yes')).toBeInTheDocument();
      expect(screen.getByText('✔️')).toBeInTheDocument();
    });

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringMatching(`${API}/zoos/${zoo.slug}/visited`),
      expect.any(Object)
    );
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringMatching(`${API}/users/${userId}/animals/ids`),
      expect.any(Object)
    );
  });
});
