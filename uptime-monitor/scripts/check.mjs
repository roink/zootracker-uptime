// Node 18/20+ (uses global fetch)
import { readFile, writeFile, mkdir, cp } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { performance } from "node:perf_hooks";

const CONFIG_PATH = "config.json";
const HISTORY_PATH = "data/checks.json";
const BUILD_DATA_PATH = "dist/data/data.json";

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

function parseDuration(str) {
  if (str === "all") return Infinity;
  const m = str.match(/^(\d+)([hdmy])$/); // h=hours,d=days,m=months(30d),y=years(365d)
  if (!m) throw new Error(`Invalid duration: ${str}`);
  const n = Number(m[1]);
  const unit = m[2];
  const day = 24 * 60 * 60 * 1000;
  if (unit === "h") return n * 60 * 60 * 1000;
  if (unit === "d") return n * day;
  if (unit === "m") return n * 30 * day;
  if (unit === "y") return n * 365 * day;
}

async function ensureDir(p) {
  await mkdir(p, { recursive: true });
}

async function readJson(path, fallback) {
  try {
    const raw = await readFile(path, "utf8");
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

async function writeJson(path, obj) {
  await ensureDir(dirname(path));
  await writeFile(path, JSON.stringify(obj, null, 2) + "\n", "utf8");
}

async function pingOnce({ url, method = "GET", timeoutMs = 10000 }) {
  const controller = new AbortController();
  const to = setTimeout(() => controller.abort(), timeoutMs);

  const started = performance.now();
  let ok = false, status = null, err = null;
  try {
    const res = await fetch(url, {
      method,
      redirect: "follow",
      cache: "no-store",
      headers: { "user-agent": "zootracker-uptime/1.0 (+github actions)" },
      signal: controller.signal
    });
    status = res.status;
    ok = res.ok;
    // Drain body to finish timing even if we don't use it
    try { await res.arrayBuffer(); } catch {}
  } catch (e) {
    err = e.message || String(e);
  } finally {
    clearTimeout(to);
  }
  const ms = Math.round(performance.now() - started);
  return { t: new Date().toISOString(), ok, status, ms, error: err };
}

function computeStats(entries, windows) {
  const byWindow = {};
  const now = Date.now();
  for (const w of windows) {
    const winMs = parseDuration(w);
    const subset = !isFinite(winMs) ? entries : entries.filter(e => (now - Date.parse(e.t)) <= winMs);
    const total = subset.length;
    const up = subset.filter(e => e.ok).length;
    const uptime = total ? +(100 * up / total).toFixed(3) : null;
    const avgMs = total ? Math.round(subset.reduce((s, e) => s + (e.ms ?? 0), 0) / total) : null;
    byWindow[w] = { total, up, uptimePercent: uptime, avgMs };
  }
  return byWindow;
}

async function main() {
  const cfg = await readJson(CONFIG_PATH, null);
  if (!cfg) throw new Error("Missing config.json");

  const history = existsSync(HISTORY_PATH)
    ? await readJson(HISTORY_PATH, { checks: {} })
    : { checks: {} };

  for (const c of cfg.checks) {
    const rec = await pingOnce(c);
    if (!history.checks[c.name]) history.checks[c.name] = [];
    history.checks[c.name].push(rec);
    // Optional: cap to last 200k points to keep file size in check
    if (history.checks[c.name].length > 200000) {
      history.checks[c.name] = history.checks[c.name].slice(-200000);
    }
    // Gentle pacing if you add many checks
    await sleep(50);
  }

  await writeJson(HISTORY_PATH, history);

  // Build a lightweight data.json for the static site
  const lastRunUTC = new Date().toISOString();
  const summary = {};
  const series = {};

  for (const c of cfg.checks) {
    const entries = history.checks[c.name] || [];
    summary[c.name] = computeStats(entries, cfg.timespans);
    series[c.name] = entries.map(e => ({ t: e.t, ms: e.ms, ok: e.ok, status: e.status }));
  }

  const siteData = {
    siteName: cfg.siteName,
    baseUrl: cfg.baseUrl,
    lastRunUTC,
    checks: cfg.checks.map(c => ({ name: c.name, url: c.url })),
    summary,
    series
  };

  await ensureDir("dist/data");
  await writeJson(BUILD_DATA_PATH, siteData);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});

