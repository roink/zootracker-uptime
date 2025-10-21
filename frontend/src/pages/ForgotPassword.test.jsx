import '@testing-library/jest-dom';
import { screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Routes, Route } from 'react-router-dom';
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';

import { renderWithRouter } from '../test-utils/router.jsx';
import { loadLocale } from '../i18n.js';
import ForgotPasswordPage from './ForgotPassword.jsx';

vi.mock('../components/Seo', () => ({ default: () => null }));

function renderForgot(route = '/en/forgot-password') {
  return renderWithRouter(
    (
      <Routes>
        <Route path="/:lang/forgot-password" element={<ForgotPasswordPage />} />
      </Routes>
    ),
    { route }
  );
}

describe('ForgotPasswordPage', () => {
  beforeEach(async () => {
    await loadLocale('en');
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });

  it('submits the email and shows a neutral success screen', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 202,
      json: () =>
        Promise.resolve({
          detail:
            "If an account exists for that email, we'll send password reset instructions shortly.",
        }),
    });
    vi.stubGlobal('fetch', fetchMock);

    renderForgot();

    const user = userEvent.setup();
    const emailField = await screen.findByLabelText('Email address');
    await user.type(emailField, 'alice@example.com');
    const submit = screen.getByRole('button', { name: 'Send reset link' });
    await user.click(submit);

    const success = await screen.findByRole('status');
    expect(success).toHaveTextContent(
      'If an account exists for alice@example.com, we’ll email password reset instructions shortly.'
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/auth\/password\/forgot$/);
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({ email: 'alice@example.com' });
  });

  it('announces rate limits with a warning alert', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: () => Promise.resolve({}),
    });
    vi.stubGlobal('fetch', fetchMock);

    renderForgot();

    const user = userEvent.setup();
    const emailField = await screen.findByLabelText('Email address');
    await user.type(emailField, 'bob@example.com');
    await user.click(screen.getByRole('button', { name: 'Send reset link' }));

    const alert = await screen.findByRole('status');
    expect(alert).toHaveClass('alert', 'alert-warning');
    expect(alert).toHaveTextContent('Too many reset requests. Please wait a minute before trying again.');
    expect(document.activeElement).toBe(alert);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
