import '@testing-library/jest-dom/vitest';
import { beforeEach, afterEach } from 'vitest';
import { loadLocale } from '../src/i18n.js';
import { clearStoredAuth } from '../src/test-utils/auth.js';

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
