// @ts-nocheck
import '@testing-library/jest-dom';
import { cleanup, screen } from '@testing-library/react';
import { Routes, Route, useLocation } from 'react-router-dom';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import i18n from '../i18n';
import ResetPasswordRedirect from './ResetPasswordRedirect';
import { renderWithRouter } from '../test-utils/router';

function LocationProbe() {
  const location = useLocation();
  return (
    <div data-testid="location">{`${location.pathname}${location.search}`}</div>
  );
}

describe('ResetPasswordRedirect', () => {
  let storageMock;
  let detectSpy;

  beforeEach(() => {
    storageMock = {
      getItem: vi.fn(() => 'de'),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    };
    vi.stubGlobal('localStorage', storageMock);
    detectSpy = vi
      .spyOn(i18n.services.languageDetector, 'detect')
      .mockReturnValue('en-US');
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });

  it('redirects to the localized reset password route and keeps the token parameter', async () => {
    renderWithRouter(
      (
        <Routes>
          <Route
            path="/reset-password"
            element={(
              <>
                <ResetPasswordRedirect />
                <LocationProbe />
              </>
            )}
          />
          <Route path="/:lang/reset-password" element={<LocationProbe />} />
        </Routes>
      ),
      { route: '/reset-password?token=test-token' }
    );

    await screen.findByText('/de/reset-password?token=test-token');

    expect(storageMock.getItem).toHaveBeenCalledWith('lang');
    expect(detectSpy).toHaveBeenCalled();
  });
});
