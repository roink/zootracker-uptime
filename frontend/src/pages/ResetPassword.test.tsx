// @ts-nocheck
import '@testing-library/jest-dom';
import { screen, cleanup, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Routes, Route } from 'react-router-dom';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { renderWithRouter } from '../test-utils/router';
import { loadLocale } from '../i18n';
import ResetPasswordPage from './ResetPassword';

vi.mock('../components/Seo', () => ({ default: () => null }));

function renderReset(route = '/en/reset-password') {
  return renderWithRouter(
    (
      <Routes>
        <Route path="/:lang/reset-password" element={<ResetPasswordPage />} />
      </Routes>
    ),
    { route }
  );
}

describe('ResetPasswordPage', () => {
  let storageMock;

  beforeEach(async () => {
    await loadLocale('en');
    storageMock = {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    };
    vi.stubGlobal('sessionStorage', storageMock);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });

  it('requires a token before showing the form', async () => {
    renderReset('/en/reset-password');

    const warning = await screen.findByRole('alert');
    expect(warning).toHaveTextContent('This reset link is invalid or has expired. Request a new password reset email to continue.');
    expect(warning).toHaveClass('alert-warning');
  });

  it('submits a new password and shows the success confirmation', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ status: 'valid' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 202,
        json: () =>
          Promise.resolve({ detail: 'If the reset token is valid, your password has been updated.' }),
      });
    vi.stubGlobal('fetch', fetchMock);
    storageMock.getItem.mockReturnValueOnce('a•••e@example.com');

    renderReset('/en/reset-password?token=test-token&email=alice@example.com');

    const user = userEvent.setup();
    const passwordField = await screen.findByLabelText('New password');
    const confirmField = screen.getByLabelText('Confirm new password');
    await user.type(passwordField, 'password123');
    await user.type(confirmField, 'password123');
    await user.click(screen.getByRole('button', { name: 'Save new password' }));

    const success = await screen.findByRole('status');
    const heading = within(success).getByRole('heading', { level: 2, name: 'Password updated' });
    expect(heading).toBeInTheDocument();
    expect(success).toHaveTextContent(
      'Your ZooTracker password for a•••e@example.com has been updated. You can now sign in with your new password.'
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [statusUrl, statusOptions] = fetchMock.mock.calls[0];
    expect(statusUrl).toMatch(/\/auth\/password\/reset\/status\?token=test-token$/);
    expect(statusOptions).toBeUndefined();
    const [url, options] = fetchMock.mock.calls[1];
    expect(url).toMatch(/\/auth\/password\/reset$/);
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({
      token: 'test-token',
      password: 'password123',
      confirmPassword: 'password123',
    });
    expect(storageMock.getItem).toHaveBeenCalledWith('ztr_password_reset_hint');
    expect(storageMock.removeItem).toHaveBeenCalledWith('ztr_password_reset_hint');
  });

  it('shows a rate limit warning when the API throttles attempts', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ status: 'valid' }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 429,
        json: () => Promise.resolve({}),
      });
    vi.stubGlobal('fetch', fetchMock);

    renderReset('/en/reset-password?token=another-token');

    const user = userEvent.setup();
    const passwordField = await screen.findByLabelText('New password');
    const confirmField = screen.getByLabelText('Confirm new password');
    await user.type(passwordField, 'password123');
    await user.type(confirmField, 'password123');
    await user.click(screen.getByRole('button', { name: 'Save new password' }));

    const alert = await screen.findByRole('status');
    expect(alert).toHaveClass('alert', 'alert-warning');
    expect(alert).toHaveTextContent('Too many attempts. Please wait and try again.');
    expect(document.activeElement).toBe(alert);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(storageMock.getItem).not.toHaveBeenCalled();
    expect(storageMock.removeItem).not.toHaveBeenCalled();
  });

  it('alerts when the reset token was already used', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: () => Promise.resolve({ status: 'consumed' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    renderReset('/en/reset-password?token=used-token');

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(
      'This reset link has already been used. Request a new password reset email to continue.'
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.queryByLabelText('New password')).not.toBeInTheDocument();
  });
});
