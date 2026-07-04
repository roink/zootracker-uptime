# ZooTracker Uptime

**Live status:**  **https://roink.github.io/zootracker-uptime/**  
**ZooTracker app:**  **https://zootracker.app/**

A minimal uptime monitor powered by **GitHub Actions** and **GitHub Pages**. It pings your endpoint every 5 minutes, commits history and site data (`data/checks.json`, `data/data.json`), and publishes a static status site (`/site` → `dist/`) showing uptime (24h / 7d / 30d / 1y / all) and response-time charts.

---

## Features

- 5-minute scheduled checks (best-effort, UTC)  
- History persisted in Git (simple, portable)  
- Static status site (no backend) with Chart.js graphs  
- Lightweight Node script (`scripts/check.mjs`) using `fetch` + 10s timeout  
- GitHub Actions cache for speed (auto-evicts if idle)

---

## How it works

- **Schedule:** A workflow runs on cron `*/5 * * * *` (UTC). Minute-level timing can drift slightly under load.  
- **Ping:** `scripts/check.mjs` performs a request with a 10s timeout and appends records like `{ t, ok, status, ms }` to `data/checks.json`.  
- **History:** Response-time data lives in Git for long-term retention.  
- **Site data:** The check script writes `data/data.json` for the frontend.  
- **Deploy:** Publishing runs in a separate workflow that builds `dist/`, uploads with `actions/upload-pages-artifact`, and deploys with `actions/deploy-pages`.  

---

## Quick start

1. **Create a repo** (e.g., `zootracker-uptime`) and copy these files.  
2. **Configure** `config.json`  
   - `baseUrl`: `/<repo-name>` (change if using a custom domain).  
   - Update your checks list if needed.  
3. **Enable Pages:** _Settings → Pages_ → **Build and deployment** = **GitHub Actions**.  
4. **Push to `main`:** The monitor workflow will:  
   - Run every 5 minutes (and on manual dispatch)  
   - Commit growing history to `data/checks.json` and `data/data.json`  
5. **Pages publishing:** The publish workflow runs on pushes that change site or generated data and deploys to GitHub Pages.  
6. **Open the live status:** Use the Pages URL printed by the publish workflow output (also shown in _Settings → Pages_).

---

## Local development

- Install deps: `npm ci` (or `npm install`)  
- Run a one-off check (if you expose a script/flag): `node scripts/check.mjs`  
- Build the site data (if separate): `node scripts/build-site.mjs`  
- Preview `site/index.html` (open in a local static server)

---

## Uptime math

For each window (24h, 7d, 30d, 365d, all):

- **Uptime %** = `up / total * 100`, where `up` = number of checks with `response.ok === true`.  
  (Timeouts or network errors count as **down**.)  
- **avgMs** = mean of response times within the window.

---

## Customizing the UI

- Tweak styles in `site/styles.css` and markup in `site/index.html`.  
- `site/app.js` renders per-check cards and a Chart.js line chart.

---

## Caveats & tips

- **Schedules are best-effort & UTC.** The shortest supported interval is 5 minutes; runs may drift slightly.  
- **Caches are ephemeral.** GitHub evicts cache entries not accessed for ~7 days and caps repo cache storage; your durable data is the Git history.  
- **Deploy from a dedicated job.** Use `upload-pages-artifact` + `deploy-pages` for the recommended Pages flow.  
