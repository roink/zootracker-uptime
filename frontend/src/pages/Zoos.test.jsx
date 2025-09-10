import React from 'react';
import '@testing-library/jest-dom';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
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

  it('filters zoos by visit status', async () => {
    const zoos = [
      { id: '1', name: 'Visited Zoo', address: '', city: '' },
      { id: '2', name: 'New Zoo', address: '', city: '' },
    ];
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
});
