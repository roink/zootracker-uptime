// @ts-nocheck
import React from 'react';
import '@testing-library/jest-dom';
import { screen, cleanup } from '@testing-library/react';
import { Routes, Route } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { renderWithRouter } from '../test-utils/router';
import { loadLocale } from '../i18n';
import ContactPage from './Contact';

vi.mock('../components/Seo', () => ({ default: () => null }));

function renderContact(route) {
  return renderWithRouter(
    (
      <Routes>
        <Route path="/:lang/contact" element={<ContactPage />} />
      </Routes>
    ),
    { route }
  );
}

describe('ContactPage translations', () => {
  it('renders localized headings and privacy notice links', async () => {
    await loadLocale('en');
    const english = renderContact('/en/contact');
    const headingEn = await screen.findByRole('heading', {
      level: 2,
      name: 'Contact',
    });
    expect(headingEn).toBeInTheDocument();
    const privacyEn = screen.getByRole('link', { name: 'Data Protection Statement' });
    expect(privacyEn).toHaveAttribute('href', '/en/data-protection');
    const legalNoticeEn = screen.getByRole('link', { name: 'Legal Notice' });
    expect(legalNoticeEn).toHaveAttribute('href', '/en/legal-notice');
    english.unmount();
    cleanup();

    await loadLocale('de');
    const german = renderContact('/de/contact');
    const headingDe = await screen.findByRole('heading', {
      level: 2,
      name: 'Kontakt',
    });
    expect(headingDe).toBeInTheDocument();
    const privacyDe = screen.getByRole('link', { name: 'Datenschutzerklärung' });
    expect(privacyDe).toHaveAttribute('href', '/de/data-protection');
    const impressumDe = screen.getByRole('link', { name: 'Impressum' });
    expect(impressumDe).toHaveAttribute('href', '/de/legal-notice');
    german.unmount();
  });
});

describe('ContactPage form behavior', () => {
  let nowSpy;

  beforeEach(async () => {
    nowSpy = vi.spyOn(Date, 'now').mockImplementation(() => 0);
    await loadLocale('en');
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });

  it('focuses the status alert when the API reports validation errors', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: () => Promise.resolve({ detail: 'validation_error' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    renderContact('/en/contact');

    const user = userEvent.setup();
    const nameField = await screen.findByLabelText('Name');
    await user.type(nameField, 'Alice Example');
    await user.type(await screen.findByLabelText('Email'), 'alice@example.com');
    await user.type(await screen.findByLabelText('Message'), 'Hello there friend!');
    nowSpy.mockImplementation(() => 5000);
    await user.click(await screen.findByRole('button', { name: 'Send' }));

    const alert = await screen.findByRole('status');
    expect(alert).toHaveClass('alert', 'alert-danger');
    expect(alert).toHaveAttribute('aria-live', 'polite');
    expect(alert).toHaveTextContent('Please check the form and try again.');
    expect(document.activeElement).toBe(alert);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, options] = fetchMock.mock.calls[0];
    const payload = JSON.parse(options.body);
    expect(payload).toEqual({
      name: 'Alice Example',
      email: 'alice@example.com',
      message: 'Hello there friend!',
    });
  });

  it('announces rate limiting with a warning alert that receives focus', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 429 });
    vi.stubGlobal('fetch', fetchMock);

    renderContact('/en/contact');

    const user = userEvent.setup();
    const nameField = await screen.findByLabelText('Name');
    await user.type(nameField, 'Alice Example');
    await user.type(await screen.findByLabelText('Email'), 'alice@example.com');
    await user.type(await screen.findByLabelText('Message'), 'Hello there friend!');
    nowSpy.mockImplementation(() => 5000);
    await user.click(await screen.findByRole('button', { name: 'Send' }));

    const alert = await screen.findByRole('status');
    expect(alert).toHaveClass('alert', 'alert-warning');
    expect(document.activeElement).toBe(alert);
    expect(alert).toHaveAttribute('aria-live', 'polite');
    expect(alert).toHaveTextContent('You are sending messages too fast. Please wait a minute and try again.');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
