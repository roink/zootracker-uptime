import '@testing-library/jest-dom/vitest';
import { loadLocale } from '../src/i18n.js';

// Load default English translations for tests
await loadLocale('en');
