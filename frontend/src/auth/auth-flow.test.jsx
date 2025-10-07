import { useEffect } from 'react';
import { fireEvent, waitFor, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithRouter } from '../test-utils/router.jsx';
import useAuthFetch from '../hooks/useAuthFetch.js';
import { useAuth } from './AuthContext.jsx';
import { createTestToken } from '../test-utils/auth.js';

const server = setupServer(
  http.post(/\/auth\/refresh$/, () =>
    HttpResponse.json({ detail: 'no session' }, { status: 401 })
  ),
  http.post(/\/auth\/logout$/, () => HttpResponse.json({}, { status: 204 }))
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function FetchHarness({ token, endpoint = '/protected', onFetched }) {
  const authFetch = useAuthFetch();
  const { login, isAuthenticated } = useAuth();

  useEffect(() => {
    login({ token, user: { id: 'user-1', email: 'user@example.com' }, expiresIn: 3600 });
  }, [login, token]);

  return (
    <div>
      <div data-testid="auth-status">{isAuthenticated ? 'authed' : 'guest'}</div>
      <button
        type="button"
        onClick={async () => {
          const response = await authFetch(endpoint);
          onFetched?.(response);
        }}
      >
        fetch
      </button>
    </div>
  );
}

function AuthStatus() {
  const { isAuthenticated } = useAuth();
  return <div data-testid="auth-status">{isAuthenticated ? 'authed' : 'guest'}</div>;
}

describe('useAuthFetch integration', () => {
  it('attaches the bearer token when authenticated', async () => {
    const headers = [];
    server.use(
      http.get('/protected', ({ request }) => {
        headers.push(request.headers.get('authorization'));
        return HttpResponse.json({ ok: true });
      })
    );

    const token = createTestToken();
    const onFetched = vi.fn();
    renderWithRouter(<FetchHarness token={token} onFetched={onFetched} />);

    const trigger = await screen.findByRole('button', { name: 'fetch' });
    fireEvent.click(trigger);

    await waitFor(() => expect(onFetched).toHaveBeenCalledTimes(1));
    expect(headers).toEqual([`Bearer ${token}`]);
    expect(screen.getByTestId('auth-status').textContent).toBe('authed');
  });

  it('logs out once on 401 and stops sending the header', async () => {
    const headers = [];
    let callCount = 0;
    server.use(
      http.get('/protected', ({ request }) => {
        callCount += 1;
        headers.push(request.headers.get('authorization'));
        if (callCount === 1) {
          return HttpResponse.json({ detail: 'unauthorized' }, { status: 401 });
        }
        return HttpResponse.json({ ok: true });
      })
    );

    const token = createTestToken();
    const onFetched = vi.fn();
    renderWithRouter(<FetchHarness token={token} onFetched={onFetched} />);

    const trigger = await screen.findByRole('button', { name: 'fetch' });
    fireEvent.click(trigger);
    await waitFor(() => expect(onFetched).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByTestId('auth-status').textContent).toBe('guest'));

    fireEvent.click(trigger);
    await waitFor(() => expect(onFetched).toHaveBeenCalledTimes(2));
    expect(headers[0]).toBe(`Bearer ${token}`);
    expect(headers[1]).toBeNull();
  });

  it('does not clear auth state on 403 responses', async () => {
    const headers = [];
    server.use(
      http.get('/protected', ({ request }) => {
        headers.push(request.headers.get('authorization'));
        return HttpResponse.json({ detail: 'forbidden' }, { status: 403 });
      })
    );

    const token = createTestToken();
    const onFetched = vi.fn();
    renderWithRouter(<FetchHarness token={token} onFetched={onFetched} />);

    const trigger = await screen.findByRole('button', { name: 'fetch' });
    fireEvent.click(trigger);
    await waitFor(() => expect(onFetched).toHaveBeenCalledTimes(1));

    expect(headers).toEqual([`Bearer ${token}`]);
    expect(screen.getByTestId('auth-status').textContent).toBe('authed');
  });

  it('remains logged out when refresh fails during boot', async () => {
    renderWithRouter(<AuthStatus />);

    await waitFor(() => expect(screen.getByTestId('auth-status').textContent).toBe('guest'));
  });
});
