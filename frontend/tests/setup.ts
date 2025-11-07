// @ts-nocheck
import '@testing-library/jest-dom/vitest';
import { beforeEach, afterEach, vi } from 'vitest';

import { loadLocale } from '../src/i18n.js';
import { clearStoredAuth } from '../src/test-utils/auth.js';

// Set React act environment flag for React 19
if (!globalThis.IS_REACT_ACT_ENVIRONMENT) {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
}

// Provide a minimal URL API so maplibre can initialize in the test environment.
if (typeof window !== 'undefined') {
  type URLWithBlobHelpers = typeof window.URL & {
    createObjectURL?: (...args: unknown[]) => string;
    revokeObjectURL?: (...args: unknown[]) => void;
  };
  class MockURL {}
  const URLConstructor = (window.URL ?? MockURL) as URLWithBlobHelpers;
  if (!URLConstructor.createObjectURL) {
    URLConstructor.createObjectURL = vi.fn(() => 'blob:mock-url');
  }
  if (!URLConstructor.revokeObjectURL) {
    URLConstructor.revokeObjectURL = vi.fn();
  }
  window.URL = URLConstructor;
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

afterEach(() => {
  clearStoredAuth();
});

if (typeof URL.createObjectURL !== 'function') {
  Object.defineProperty(URL, 'createObjectURL', {
    value: () => 'blob:mock-url',
    writable: true,
    configurable: true,
  });
}

// Load default English translations for tests
await loadLocale('en');
