# API package overview

The `app.api` package exposes HTTP route handlers grouped by feature area.
Modules are organised as:

- `animals.py`, `zoos.py`, `visits.py`, and `sightings.py` – CRUD endpoints for domain entities.
- `users.py` & `auth.py` – account management, authentication, and password reset flows.
- `contact.py` & `site.py` – public contact form and site-wide summary endpoints.
- `images.py` & `location.py` – media upload/retrieval and geospatial endpoints.
- `deps.py` – dependency injection utilities shared by multiple routers.
- `_validation.py` – custom request/response validators centralised for reuse.

Routers should stay small and delegate business logic to `app.models`, `app.schemas`, or helper modules.
