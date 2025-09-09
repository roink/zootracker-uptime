import React from 'react';
import '@testing-library/jest-dom';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../hooks/useAuthFetch', () => ({ default: () => fetch }));
vi.mock('../components/Seo', () => ({ default: () => null }));

import ZoosPage from './Zoos.jsx';
import { API } from '../api';

describe('ZoosPage', () => {
  beforeEach(() => {
    vi.stubGlobal('navigator', {
      geolocation: { getCurrentPosition: (_s, e) => e() },
    });
  });

  it('loads visited zoo IDs and marks visited zoos', async () => {
    const zoos = [{ id: '1', name: 'A Zoo', address: '', city: '' }];
    const visited = ['1'];
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(zoos) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(visited) });
    global.fetch = fetchMock;

    render(
      <MemoryRouter>
        <ZoosPage token="t" />
      </MemoryRouter>
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(`${API}/zoos`));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(`${API}/visits/ids`));
    const badges = await screen.findAllByText('Visited', { selector: 'span' });
    expect(badges[0]).toBeInTheDocument();
  });
});
