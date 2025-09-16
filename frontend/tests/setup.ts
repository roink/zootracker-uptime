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

// Load default English translations for tests
await loadLocale('en');
