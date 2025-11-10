# Frontend package overview

The `frontend/` directory contains a Vite-powered React application for tracking zoo visits and animal sightings.

Key directories:
- `src/components/` – shared React components
- `src/pages/` – route pages
- `src/styles/` – custom CSS loaded by `main.jsx`
- `src/locales/` – translation files (English and German)
- `src/api.ts` – API configuration
- `src/auth/` – authentication context and helpers

## Testing and validation

When making changes to the frontend, always run:

1. **Linting**: `pnpm --filter zoo-tracker-frontend run lint`
2. **Type checking**: `pnpm --filter zoo-tracker-frontend run typecheck`
3. **Tests**: `pnpm --filter zoo-tracker-frontend run test`

The test command runs both unit tests (Vitest) and end-to-end tests (Playwright).
