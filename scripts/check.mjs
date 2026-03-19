// Node 20+ (uses global fetch)
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname } from "node:path";
import { performance } from "node:perf_hooks";

const CONFIG_PATH = "config.json";
const HISTORY_PATH = "data/checks.json";
const BUILD_DATA_PATH = "dist/data/data.json";
const HEADER_ALLOWLIST = [
  "server",
  "content-type",
  "cache-control",
  "content-length",
  "etag",
  "age",
  "x-request-id",
  "x-cache-status",
  "cf-cache-status",
  "cf-ray",
];
const BODY_SAMPLE_LIMIT = 400;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function parseDuration(str) {
  if (str === "all") return Infinity;
  const match = str.match(/^(\d+)([hdmy])$/);
  if (!match) throw new Error(`Invalid duration: ${str}`);
  const value = Number(match[1]);
  const unit = match[2];
  const day = 24 * 60 * 60 * 1000;
  if (unit === "h") return value * 60 * 60 * 1000;
  if (unit === "d") return value * day;
  if (unit === "m") return value * 30 * day;
  if (unit === "y") return value * 365 * day;
  throw new Error(`Unsupported duration: ${str}`);
}

async function ensureDir(path) {
  await mkdir(path, { recursive: true });
}

async function readJson(path, fallback) {
  try {
    const raw = await readFile(path, "utf8");
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

async function writeJson(path, value) {
  await ensureDir(dirname(path));
  await writeFile(path, JSON.stringify(value, null, 2) + "\n", "utf8");
}

function pickHeaders(headers) {
  const out = {};
  for (const key of HEADER_ALLOWLIST) {
    const value = headers.get(key);
    if (value) out[key] = value;
  }
  return out;
}

function sanitizeBodySample(value) {
  if (typeof value !== "string" || value.length === 0) return null;
  return value.replace(/\s+/g, " ").trim().slice(0, BODY_SAMPLE_LIMIT) || null;
}

function getPathSegments(path) {
  return String(path)
    .split(".")
    .filter(Boolean)
    .map((segment) => (/^\d+$/.test(segment) ? Number(segment) : segment));
}

function hasJsonPath(value, path) {
  let current = value;
  for (const segment of getPathSegments(path)) {
    if (current === null || current === undefined) return false;
    if (typeof segment === "number") {
      if (!Array.isArray(current) || segment >= current.length) return false;
      current = current[segment];
      continue;
    }
    if (
      typeof current !== "object" ||
      !Object.prototype.hasOwnProperty.call(current, segment)
    ) {
      return false;
    }
    current = current[segment];
  }
  return true;
}

function getJsonPathValue(value, path) {
  let current = value;
  for (const segment of getPathSegments(path)) {
    if (current === null || current === undefined) return undefined;
    current = current[segment];
  }
  return current;
}

function computePercentile(values, percentile) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.floor(percentile * (sorted.length - 1));
  return sorted[index];
}

function classifyNetworkError(error) {
  if (!error) return "network";
  if (error.name === "AbortError") return "timeout";
  return "network";
}

async function maybeReadTextBody(response, expect, shouldCaptureOnFailure) {
  const contentType = response.headers.get("content-type") || "";
  const needsBody =
    Boolean(expect?.bodyIncludes?.length) ||
    Boolean(expect?.jsonPaths?.length) ||
    Boolean(expect?.jsonMin && Object.keys(expect.jsonMin).length) ||
    shouldCaptureOnFailure;
  const isTextual =
    contentType.includes("json") ||
    contentType.includes("text/") ||
    contentType.includes("xml") ||
    contentType.includes("html");
  if (!needsBody || !isTextual) return null;
  return response.text();
}

function evaluateExpectations({ response, headers, bodyText, expect }) {
  if (!expect) {
    return { ok: response.ok, reason: response.ok ? null : "http_status", detail: null };
  }

  const expectedStatuses = Array.isArray(expect.status)
    ? expect.status
    : typeof expect.status === "number"
      ? [expect.status]
      : null;
  if (expectedStatuses && !expectedStatuses.includes(response.status)) {
    return {
      ok: false,
      reason: "status",
      detail: `Expected status ${expectedStatuses.join(", ")}, got ${response.status}`,
    };
  }

  if (!expectedStatuses && !response.ok) {
    return {
      ok: false,
      reason: "http_status",
      detail: `HTTP ${response.status}`,
    };
  }

  const contentType = headers["content-type"] || "";
  if (
    typeof expect.contentTypeIncludes === "string" &&
    !contentType.toLowerCase().includes(expect.contentTypeIncludes.toLowerCase())
  ) {
    return {
      ok: false,
      reason: "content_type",
      detail: `Expected content-type to include "${expect.contentTypeIncludes}"`,
    };
  }

  if (Array.isArray(expect.headerExists)) {
    for (const name of expect.headerExists) {
      if (!headers[name.toLowerCase()]) {
        return {
          ok: false,
          reason: "header_missing",
          detail: `Missing header ${name}`,
        };
      }
    }
  }

  if (Array.isArray(expect.bodyIncludes)) {
    for (const snippet of expect.bodyIncludes) {
      if (!bodyText || !bodyText.includes(snippet)) {
        return {
          ok: false,
          reason: "body_mismatch",
          detail: `Body is missing "${snippet}"`,
        };
      }
    }
  }

  if (
    (Array.isArray(expect.jsonPaths) && expect.jsonPaths.length > 0) ||
    (expect.jsonMin && Object.keys(expect.jsonMin).length > 0)
  ) {
    let parsed;
    try {
      parsed = bodyText ? JSON.parse(bodyText) : null;
    } catch {
      return {
        ok: false,
        reason: "json_parse",
        detail: "Response body is not valid JSON",
      };
    }

    for (const path of expect.jsonPaths || []) {
      if (!hasJsonPath(parsed, path)) {
        return {
          ok: false,
          reason: "json_path_missing",
          detail: `Missing JSON path ${path}`,
        };
      }
    }

    for (const [path, minValue] of Object.entries(expect.jsonMin || {})) {
      const actual = getJsonPathValue(parsed, path);
      if (typeof actual !== "number" || actual < minValue) {
        return {
          ok: false,
          reason: "json_min",
          detail: `Expected ${path} >= ${minValue}`,
        };
      }
    }
  }

  return { ok: true, reason: null, detail: null };
}

async function pingOnce(check) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), check.timeoutMs || 10000);
  const started = performance.now();

  let response = null;
  let error = null;

  try {
    response = await fetch(check.url, {
      method: check.method || "GET",
      redirect: "follow",
      cache: "no-store",
      headers: { "user-agent": "zootracker-uptime/2.0 (+github actions)" },
      signal: controller.signal,
    });

    const headers = pickHeaders(response.headers);
    const bodyText = await maybeReadTextBody(
      response.clone(),
      check.expect,
      !response.ok,
    );
    const assertion = evaluateExpectations({
      response,
      headers,
      bodyText,
      expect: check.expect,
    });
    const ms = Math.round(performance.now() - started);

    return {
      t: new Date().toISOString(),
      ok: assertion.ok,
      status: response.status,
      ms,
      method: check.method || "GET",
      phase: check.phase || "other",
      finalUrl: response.url,
      headers,
      assertion: assertion.reason,
      detail: assertion.detail,
      bodySample: assertion.ok ? null : sanitizeBodySample(bodyText),
      error: null,
    };
  } catch (caughtError) {
    error = caughtError;
    const ms = Math.round(performance.now() - started);
    return {
      t: new Date().toISOString(),
      ok: false,
      status: null,
      ms,
      method: check.method || "GET",
      phase: check.phase || "other",
      finalUrl: check.url,
      headers: {},
      assertion: classifyNetworkError(caughtError),
      detail: caughtError?.message || String(caughtError),
      bodySample: null,
      error: caughtError?.message || String(caughtError),
    };
  } finally {
    clearTimeout(timeout);
    if (response && check.method !== "HEAD") {
      try {
        await response.arrayBuffer();
      } catch {
        // Ignore body drain failures.
      }
    }
  }
}

function computeStats(entries, windows, slowThresholdMs) {
  const byWindow = {};
  const now = Date.now();

  for (const window of windows) {
    const windowMs = parseDuration(window);
    const subset = Number.isFinite(windowMs)
      ? entries.filter((entry) => now - Date.parse(entry.t) <= windowMs)
      : entries;
    const successes = subset.filter(
      (entry) => entry.ok && typeof entry.ms === "number" && Number.isFinite(entry.ms),
    );
    const latencyValues = successes.map((entry) => entry.ms);
    const total = subset.length;
    const failureCount = subset.filter((entry) => !entry.ok).length;
    const slowCount = latencyValues.filter((value) => value >= slowThresholdMs).length;
    const uptimePercent = total ? +(100 * successes.length / total).toFixed(3) : null;
    const avgMs = latencyValues.length
      ? Math.round(latencyValues.reduce((sum, value) => sum + value, 0) / latencyValues.length)
      : null;
    const medianMs = computePercentile(latencyValues, 0.5);
    const p95Ms = computePercentile(latencyValues, 0.95);

    byWindow[window] = {
      total,
      up: successes.length,
      failures: failureCount,
      slowCount,
      uptimePercent,
      avgMs,
      medianMs,
      p95Ms,
    };
  }

  return byWindow;
}

function getConsecutiveFailureCount(entries) {
  let count = 0;
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    if (entries[index].ok) break;
    count += 1;
  }
  return count;
}

function summarizeLatest(check, entries) {
  const latest = entries.at(-1) || null;
  const lastFailure = [...entries].reverse().find((entry) => !entry.ok) || null;
  const lastSuccess = [...entries].reverse().find((entry) => entry.ok) || null;

  return {
    check: check.name,
    phase: check.phase || "other",
    latest,
    lastFailure,
    lastSuccess,
    consecutiveFailures: getConsecutiveFailureCount(entries),
    retainedSamples: entries.length,
  };
}

function convertLegacyEntry(entry, check) {
  return {
    t: entry.t,
    ok: entry.ok,
    status: entry.status,
    ms: entry.ms,
    method: check.method || "GET",
    phase: check.phase || "frontend",
    finalUrl: check.url,
    headers: entry.headers || {},
    assertion: entry.ok ? null : "legacy",
    detail: entry.error || null,
    bodySample: null,
    error: entry.error || null,
  };
}

function migrateLegacyHistory(history, config) {
  const LEGACY_KEY = "ZooTracker";
  const TARGET_NAME = "Frontend HTML";
  if (!history.checks[LEGACY_KEY]) {
    return;
  }

  const targetCheck = config.checks.find((check) => check.name === TARGET_NAME);
  if (!targetCheck) {
    return;
  }

  const existing = history.checks[TARGET_NAME] || [];
  const migrated = history.checks[LEGACY_KEY].map((entry) =>
    convertLegacyEntry(entry, targetCheck),
  );

  const combined = [...migrated, ...existing];
  combined.sort((a, b) => {
    const left = Date.parse(a.t);
    const right = Date.parse(b.t);
    return left - right;
  });

  history.checks[TARGET_NAME] = combined;
  delete history.checks[LEGACY_KEY];
}

async function main() {
  const config = await readJson(CONFIG_PATH, null);
  if (!config) throw new Error("Missing config.json");

  const history = existsSync(HISTORY_PATH)
    ? await readJson(HISTORY_PATH, { checks: {} })
    : { checks: {} };
  migrateLegacyHistory(history, config);
  const historyLimit = Number(config.historyLimit) || 18000;
  const slowThresholdMs = Number(config.slowThresholdMs) || 1000;

  for (const check of config.checks) {
    const record = await pingOnce(check);
    if (!history.checks[check.name]) history.checks[check.name] = [];
    history.checks[check.name].push(record);
    if (history.checks[check.name].length > historyLimit) {
      history.checks[check.name] = history.checks[check.name].slice(-historyLimit);
    }
    await sleep(75);
  }

  await writeJson(HISTORY_PATH, history);

  const summary = {};
  const series = {};
  const latest = {};
  const phaseOverview = {};

  for (const check of config.checks) {
    const entries = history.checks[check.name] || [];
    summary[check.name] = computeStats(entries, config.timespans, slowThresholdMs);
    series[check.name] = entries.map((entry) => ({
      t: entry.t,
      ok: entry.ok,
      status: entry.status,
      ms: entry.ms,
      assertion: entry.assertion || null,
      detail: entry.detail || null,
      headers: entry.headers || {},
      bodySample: entry.bodySample || null,
      method: entry.method || check.method || "GET",
      finalUrl: entry.finalUrl || check.url,
      phase: entry.phase || check.phase || "other",
    }));
    latest[check.name] = summarizeLatest(check, entries);

    const phase = check.phase || "other";
    if (!phaseOverview[phase]) {
      phaseOverview[phase] = { total: 0, healthy: 0, degraded: 0 };
    }
    phaseOverview[phase].total += 1;
    if (latest[check.name].latest?.ok) {
      phaseOverview[phase].healthy += 1;
    } else {
      phaseOverview[phase].degraded += 1;
    }
  }

  const siteData = {
    siteName: config.siteName,
    baseUrl: config.baseUrl,
    lastRunUTC: new Date().toISOString(),
    historyLimit,
    slowThresholdMs,
    checks: config.checks.map((check) => ({
      name: check.name,
      phase: check.phase || "other",
      description: check.description || "",
      method: check.method || "GET",
      url: check.url,
    })),
    summary,
    series,
    latest,
    phaseOverview,
  };

  await ensureDir("dist/data");
  await writeJson(BUILD_DATA_PATH, siteData);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
