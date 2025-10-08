import { describe, it, expect, vi, afterEach } from 'vitest';
import { Routes, Route } from 'react-router-dom';
import { screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HelmetProvider } from 'react-helmet-async';

import LoginPage from '../src/pages/Login.jsx';
import { renderWithRouter } from '../src/test-utils/router.jsx';

describe('LoginPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('focuses the consent checkbox and blocks the request when consent is missing', async () => {
    const user = userEvent.setup();
    const fetchSpy = vi
      .spyOn(global, 'fetch')
      .mockResolvedValue({ ok: true, json: vi.fn() });

    const helmetContext = { helmetInstances: new Set() };
    renderWithRouter(
      <HelmetProvider context={helmetContext}>
        <Routes>
          <Route path="/:lang/login" element={<LoginPage />} />
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      </HelmetProvider>,
      { initialEntries: ['/en/login#signup'] }
    );

    const signupHeading = await screen.findByRole('heading', { name: /sign up/i });
    const signupForm = signupHeading.closest('form');
    const formUtils = within(signupForm);

    await user.type(formUtils.getByPlaceholderText('Name'), 'Test User');
    await user.type(formUtils.getByPlaceholderText('Email'), 'test@example.com');
    await user.type(formUtils.getByPlaceholderText('Password'), 'supersecret');
    await user.type(formUtils.getByPlaceholderText('Confirm Password'), 'supersecret');

    const submitButton = formUtils.getByRole('button', { name: /create account/i });
    await user.click(submitButton);

    expect(fetchSpy).not.toHaveBeenCalled();

    const consentLink = formUtils.getByRole('link', {
      name: /data protection statement/i,
    });
    expect(consentLink).toHaveAttribute('href', '/en/data-protection');

    const consentCheckbox = formUtils.getByRole('checkbox', {
      name: /data protection/i,
    });
    await waitFor(() => expect(consentCheckbox).toHaveFocus());
    expect(consentCheckbox).toHaveAttribute('aria-invalid', 'true');

    expect(
      await formUtils.findByText(
        'Please accept the data protection statement to create an account.'
      )
    ).toBeVisible();
  });
});
