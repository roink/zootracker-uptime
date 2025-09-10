import { screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderWithRouter } from '../test-utils/router.jsx';
import ZooDetail from './ZooDetail';
import { API } from '../api';
vi.mock('./LazyMap', () => ({ default: () => <div data-testid="map" /> }));

describe('ZooDetail component', () => {
  const zoo = { id: 'z1', name: 'Test Zoo' };
  const userId = 'u1';
  const animalId = 'a1';

  beforeEach(() => {
    global.fetch = vi.fn((url) => {
      if (url.endsWith(`/zoos/${zoo.id}/animals`)) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([{ id: animalId, common_name: 'Lion' }]),
        });
      }
      if (url.endsWith(`/zoos/${zoo.id}/visited`)) {
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
    renderWithRouter(<ZooDetail zoo={zoo} token="t" userId={userId} />);

    await waitFor(() => {
      expect(screen.getByText('Visited? ☑️ Yes')).toBeInTheDocument();
      expect(screen.getByText('✔️')).toBeInTheDocument();
    });

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringMatching(`${API}/zoos/${zoo.id}/visited`),
      expect.any(Object)
    );
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringMatching(`${API}/users/${userId}/animals/ids`),
      expect.any(Object)
    );
  });
});
