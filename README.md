# ZooTracker Uptime (DIY)

A minimal uptime monitor built with GitHub Actions and GitHub Pages. It pings your endpoint every 5 minutes, commits history to `data/checks.json`, and publishes a static site (`/site` → `dist/`) with uptime % (24h / 7d / 30d / 1y / all) and response-time charts.

## How it works

- **Schedule**: A workflow runs on cron (`*/5 * * * *`). GitHub Actions guarantees a minimum interval of 5 minutes for scheduled workflows, but actual run time may drift slightly and is in UTC.  

- **Ping**: `scripts/check.mjs` uses Node’s `fetch` with a 10s timeout. It appends `{t, ok, status, ms}` to `data/checks.json`.

- **History**: Response-time data is **committed to git** for long-term retention.

- **Site**: The same script builds `dist/data/data.json`. The static site (Chart.js via CDN) is deployed to GitHub Pages using the official `upload-pages-artifact` + `deploy-pages` actions.

- **Caching**: The workflow caches npm files to keep runs fast; cache entries evict if not accessed for 7 days.

## Setup

1. **Create repo** (e.g., `zootracker-uptime`). Copy all files from this project.
2. **Edit** `config.json`:
   - `baseUrl`: `/<repo-name>` (change if you use a custom domain).
   - Update/check list if needed.
3. **Enable Pages**: In **Settings → Pages**, set **Build and deployment** to **GitHub Actions**.
4. **Push to `main`**. The workflow will:
   - Run every 5 minutes and on manual dispatch.
   - Commit `data/checks.json` as history grows.
   - Build and deploy the status site.
5. **Visit** the Pages URL printed in the deploy job output (or shown in Settings → Pages). The action we use exposes a `page_url`. 

## Customizing the UI

- Edit `site/styles.css` and `site/index.html`.
- `site/app.js` renders cards per check and a Chart.js line chart of response time. 

## Uptime math

- For each window (24h, 7d, 30d, 365d, all), uptime % = `up / total * 100`, where *up* = checks with `response.ok === true`. Timeouts or network errors count as down.
- `avgMs` is the mean response time inside the window (displayed subtly, can be surfaced if you want).

## Caveats

- **Schedules are best-effort**. Don’t expect to-the-minute precision for cron. 
- **Caches are ephemeral** (evicted after ~7 days of inactivity). Long-term data lives in git. 
- Pages deploys from the workflow artifact using the recommended `deploy-pages` action in a dedicated job. 

