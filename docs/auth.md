# Authentication and session lifecycle

The API now issues short-lived access tokens alongside rotating refresh
tokens. Access tokens are JWTs signed with HS256 using the secret configured
through `JWT_SECRET` (falling back to the legacy `SECRET_KEY` value). They
expire after `ACCESS_TOKEN_TTL` seconds (15 minutes by default) and are
returned to the SPA in the body of the login and refresh responses.

Refresh tokens are opaque values stored as `HttpOnly` cookies on the
`/auth` path. They are rotated on every refresh request and are never
stored in plaintext – only SHA-256 hashes (peppered with `TOKEN_PEPPER`) are
persisted in the `refresh_tokens` table. Each token tracks idle and absolute
timeouts (`REFRESH_IDLE_TTL`, `REFRESH_ABS_TTL`). Presenting a refresh token
that has already been rotated revokes the entire session family.

All responses that include tokens set `Cache-Control: no-store`/`Pragma:
no-cache`. Refresh requests must include the anti-CSRF header (`X-CSRF`) which
matches the non-HttpOnly cookie delivered alongside the refresh token.

Cookies are emitted with `SameSite` and `Secure` attributes derived from
`COOKIE_SAMESITE`/`COOKIE_SECURE`; the domain can be customised with
`COOKIE_DOMAIN`. CORS is configured to allow credentials so the SPA can send
cookies and custom headers.

The `/auth/logout` endpoint revokes the current refresh token family and clears
both cookies. Applications should always call it during sign-out.

## Running locally

Local development typically runs both the FastAPI server (e.g. on
`http://localhost:8000`) and the SPA dev server (e.g. Vite on
`http://localhost:5173`) over plain HTTP. Because secure cookies are only sent
over HTTPS, you **must** disable the secure flag while developing locally or
the browser will silently drop the refresh token and you will immediately be
logged out again. Update your `.env` file with:

```
COOKIE_SECURE=false
COOKIE_SAMESITE=Lax
ALLOWED_ORIGINS=http://localhost:5173
```

You can keep the remaining defaults from `.env.example`. Make sure to restart
the FastAPI process so the new cookie settings are applied. When running the
frontend locally, enable credentials on all fetches (`credentials: 'include'`)
so the refresh cookie is sent automatically.

## Deploying to production

For production deployments you should serve the API and SPA over HTTPS. Enable
`COOKIE_SECURE=true` (the default in `.env.example`) to require TLS for refresh
tokens and adjust `COOKIE_DOMAIN` if you need to share the session across
multiple subdomains. Set `COOKIE_SAMESITE` to `None` only when the frontend and
backend live on different sites and you already have TLS in place; otherwise
prefer `Lax` or `Strict` to minimise CSRF exposure.

Always configure a strong `JWT_SECRET` and `TOKEN_PEPPER`, store them in your
secrets manager, and rotate them periodically. In container or cloud
environments, ensure the environment variables used above are set via your
orchestration platform rather than checking them into source control. Finally,
include the production SPA origin (e.g. `https://app.example.com`) in
`ALLOWED_ORIGINS` so CORS allows cookies and custom headers from the deployed
frontend.
