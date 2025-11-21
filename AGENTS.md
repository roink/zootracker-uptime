# Agent Instructions

This repository provides a FastAPI backend for tracking zoo visits and animal sightings and a small React frontend. The backend uses a PostgreSQL database. The frontend is located under `frontend/` and is built with Vite and React. Use Bootstrap classes for styling and keep components well commented with `//` style descriptions. Prefer small components and place reusable styles in CSS files under `src/styles` instead of inline styles.

Project structure overview:

- `apps/backend/` – FastAPI backend application
  - `app/` – FastAPI application code
  - `tests/` – pytest suite for the backend
  - `requirements.txt` – Python dependencies
  - `setup_env.sh` – virtual environment setup script
- `apps/frontend/` – React/Vite web client
  - `src/components/` – shared React components
  - `src/pages/` – route pages
  - `src/styles/` – custom CSS loaded by `main.tsx`
- `docs/` – architecture and planning documents
- `deploy/` – Ansible inventories, playbooks, and nginx templates used to provision the production server. See `deploy/AGENTS.md`
  for a detailed overview of the deployment assets and configuration guidance.
- `schema.sql` – reference database schema (maintained in root for documentation)

## Running tests

For detailed instructions on running and validating tests:
- **Backend tests**: See `apps/backend/app/AGENTS.md`
- **Frontend tests**: See `apps/frontend/AGENTS.md`

Always run the relevant tests after making changes.

## Git commits

**IMPORTANT**: Never commit changes yourself. Always leave commits to the user. Stage changes with `git add` if requested, but never run `git commit`.

## Environment setup

Activate the provided virtual environment before running tests, linting, or the app. All required Python packages are already installed there.

```bash
source apps/backend/venv/bin/activate
```

If you need to recreate the environment, run:

```bash
cd apps/backend && ./setup_env.sh
```
This uses `apps/backend/requirements.txt` which must list all Python packages like `fastapi` needed to execute the backend and test suite.

## Linting and validation

- **Backend**: See `apps/backend/app/AGENTS.md` for Python linting and type checking
- **Frontend**: See `apps/frontend/AGENTS.md` for JavaScript/TypeScript linting and type checking

## Package manager

The frontend uses **pnpm** instead of npm. All `npm` commands should be replaced with `pnpm --filter zoo-tracker-frontend` when working in the root directory, or simply `pnpm` when working inside the `frontend/` directory.


## Translations

All user-facing strings in the frontend live in `apps/frontend/src/locales/<lang>/common.json`. When adding new UI text:

- Add keys to both the English and German files with descriptive names (e.g. `actions.logSighting`).
- Use `useTranslation` and `t()` in components instead of hardcoded strings.
- Update documentation if necessary and run the tests and linters.

See `docs/i18n.md` for more details on the translation workflow.

## Frontend overlays

A generic modal layout is provided in `apps/frontend/src/styles/app.css` using the
`.modal-overlay` and `.modal-box` classes. Components can use these classes to
present forms as centered overlays. Keep the modal contents narrow (max-width
around 500px) so they do not fill the entire screen on large monitors. When
opening the sighting modal from another page, pass both the ID **and** name of
the current animal and zoo in the router state. This lets the form show those
values immediately while it fetches the full lists for searching.

The dashboard now shows an **Edit** button next to each sighting. Clicking it
opens a modal overlay with the sighting pre-filled so users can update the zoo,
animal or date. The form offers **Cancel**, **Apply changes** and **Delete**
actions and is implemented using the existing `LogSighting` component. The
overlay page is mounted at `/sightings/:id/edit`.

## PWA Assets

The frontend is configured as a Progressive Web App (PWA) with icons and manifest generated from `apps/frontend/public/Buch.svg`.

- **Icon generation**: PWA assets are generated using `@vite-pwa/assets-generator` with the `minimal-2023` preset
- **Configuration**: See `apps/frontend/pwa-assets.config.js`
- **Regenerate assets**: Run `pnpm --filter zoo-tracker-frontend generate:pwa-assets` from root, or `pnpm generate:pwa-assets` from `apps/frontend/`
- **Generated files**: `pwa-64x64.png`, `pwa-192x192.png`, `pwa-512x512.png`, `maskable-icon-512x512.png`, `apple-touch-icon-180x180.png`, and `favicon.ico` in `apps/frontend/public/`
- **SVG favicon**: `favicon.svg` (copy of `Buch.svg`) provides modern SVG icon support
- **Manifest**: `apps/frontend/public/manifest.webmanifest` defines PWA metadata with both raster and SVG icon references, includes `id`, `scope`, `lang`, and `orientation` for best practices
- **HTML links**: `apps/frontend/index.html` includes multi-size ICO favicon, SVG favicon, apple-touch-icon, manifest link, and theme-color meta tag

The uptime monitor uses `favicon.ico` in `uptime-monitor/site/` but does not require PWA configuration.

