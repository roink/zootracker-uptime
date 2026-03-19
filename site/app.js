function parseDuration(str) {
  if (str === "all") return Infinity;
  const match = str.match(/^(\d+)([hdmy])$/);
  if (!match) return null;
  const value = Number(match[1]);
  const unit = match[2];
  const hour = 60 * 60 * 1000;
  if (unit === "h") return value * hour;
  if (unit === "d") return value * 24 * hour;
  if (unit === "m") return value * 30 * 24 * hour;
  if (unit === "y") return value * 365 * 24 * hour;
  return null;
}

function formatMs(value) {
  return value === null || value === undefined ? "—" : `${value} ms`;
}

function formatTimeAgo(dateString) {
  if (!dateString) return "—";
  const diffMs = Date.now() - new Date(dateString).getTime();
  const minutes = Math.max(0, Math.round(diffMs / 60000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

function formatTimestamp(dateString) {
  if (!dateString) return "—";
  return new Date(dateString).toLocaleString();
}

function formatLastUpdated(dateString) {
  const lastRun = new Date(dateString);
  const diffMs = Date.now() - lastRun.getTime();
  const minutes = Math.max(0, Math.round(diffMs / 60000));
  const unit = minutes === 1 ? "minute" : "minutes";
  return `Last updated ${minutes} ${unit} ago`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#39;");
}

function computeResponseStats(entries, slowThresholdMs) {
  const values = entries
    .filter((entry) => entry.ok)
    .map((entry) => entry.ms)
    .filter((value) => typeof value === "number" && Number.isFinite(value));
  if (!values.length) {
    return { mean: null, median: null, p95: null, slowCount: 0 };
  }

  const sorted = [...values].sort((a, b) => a - b);
  const total = values.reduce((sum, value) => sum + value, 0);
  const mean = Math.round(total / values.length);
  const mid = Math.floor(sorted.length / 2);
  const median =
    sorted.length % 2 === 0
      ? Math.round((sorted[mid - 1] + sorted[mid]) / 2)
      : sorted[mid];
  const p95Index = Math.floor(0.95 * (sorted.length - 1));
  const p95 = sorted[p95Index];
  const slowCount = values.filter((value) => value >= slowThresholdMs).length;

  return { mean, median, p95, slowCount };
}

function computeFailureRangesForSubset(subset) {
  const ranges = [];
  if (!subset.length) return ranges;

  let index = 0;
  while (index < subset.length) {
    if (subset[index].ok) {
      index += 1;
      continue;
    }

    const startIndex = index;
    while (index + 1 < subset.length && !subset[index + 1].ok) {
      index += 1;
    }
    const endIndex = index;

    const firstFail = subset[startIndex].date;
    const lastFail = subset[endIndex].date;
    const prev = startIndex > 0 ? subset[startIndex - 1].date : null;
    const next = endIndex < subset.length - 1 ? subset[endIndex + 1].date : null;

    let startTime;
    let endTime;

    if (prev && next) {
      startTime = new Date((prev.getTime() + firstFail.getTime()) / 2);
      endTime = new Date((next.getTime() + lastFail.getTime()) / 2);
    } else if (prev && !next) {
      startTime = new Date((prev.getTime() + firstFail.getTime()) / 2);
      endTime = new Date(lastFail.getTime() + (lastFail.getTime() - prev.getTime()) / 2);
    } else if (!prev && next) {
      startTime = new Date(firstFail.getTime() - (next.getTime() - firstFail.getTime()) / 2);
      endTime = new Date((next.getTime() + lastFail.getTime()) / 2);
    } else {
      startTime = new Date(firstFail.getTime());
      endTime = new Date(lastFail.getTime());
    }

    ranges.push({ start: startTime, end: endTime });
    index += 1;
  }

  return ranges;
}

function getPhaseLabel(phase) {
  const labels = {
    frontend: "Frontend",
    "api-shallow": "API shallow",
    "api-db": "API database",
    seo: "SEO",
    storage: "Storage",
  };
  return labels[phase] || phase;
}

function getStatusClass(ok) {
  return ok ? "up" : "down";
}

function renderHeaders(headers) {
  const keys = Object.keys(headers || {});
  if (!keys.length) return "<span class=\"muted\">No diagnostic headers recorded</span>";
  return keys
    .map(
      (key) =>
        `<span class="header-chip"><strong>${escapeHtml(key)}</strong>${escapeHtml(headers[key])}</span>`,
    )
    .join("");
}

function renderRecentFailures(entries) {
  const failures = entries.filter((entry) => !entry.ok).slice(-3).reverse();
  if (!failures.length) {
    return "<div class=\"muted\">No failures in retained history.</div>";
  }
  return failures
    .map((entry) => {
      const badges = [
        entry.status ? `<span class="failure-badge">HTTP ${entry.status}</span>` : "",
        entry.assertion ? `<span class="failure-badge">${entry.assertion}</span>` : "",
      ]
        .filter(Boolean)
        .join("");

      return `
        <div class="failure-item">
          <div class="failure-meta">
            <span class="failure-time">${escapeHtml(formatTimestamp(entry.t))}</span>
            <div class="failure-badges">${badges}</div>
          </div>
          ${entry.detail ? `<div class="failure-detail">${escapeHtml(entry.detail)}</div>` : ""}
        </div>
      `;
    })
    .join("");
}

function createPhaseSection(phase, overview) {
  const section = document.createElement("section");
  section.className = "phase-section";
  section.dataset.phase = phase;
  const statusText = overview.degraded
    ? `${overview.healthy} healthy, ${overview.degraded} degraded`
    : `${overview.healthy} healthy`;
  section.innerHTML = `
    <div class="phase-header">
      <div>
        <h2>${getPhaseLabel(phase)}</h2>
        <p>${statusText}</p>
      </div>
    </div>
    <div class="phase-grid"></div>
  `;
  return section;
}

async function main() {
  const data = await fetch("./data/data.json", { cache: "no-store" }).then((response) =>
    response.json(),
  );
  const titleEl = document.querySelector("#title");
  const img = titleEl.querySelector("img");
  titleEl.textContent = data.siteName || "Uptime";
  if (img) titleEl.prepend(img);
  document.querySelector("#last-run").textContent = formatLastUpdated(data.lastRunUTC);
  const checks = data.checks || [];

  const phaseHost = document.querySelector("#checks");
  const phaseSections = new Map();

  for (const [phase, overview] of Object.entries(data.phaseOverview || {})) {
    const section = createPhaseSection(phase, overview);
    phaseSections.set(phase, section);
    phaseHost.appendChild(section);
  }

  for (const check of checks) {
    const card = document.createElement("article");
    card.className = "card";
    const entries = (data.series[check.name] || []).map((entry) => ({
      ...entry,
      date: new Date(entry.t),
    }));
    const latest = data.latest[check.name] || {};
    const windows = ["24h", "7d", "30d", "all"].filter(
      (window) => data.summary[check.name]?.[window] !== undefined,
    );
    const buttons = new Map();
    let failureRanges = [];

    const latestEntry = latest.latest || null;
    const latestOk = latestEntry?.ok ?? false;
    const latestStatus = latestEntry?.status ? `HTTP ${latestEntry.status}` : "No response";
    const latestReason = latestEntry?.assertion || latestEntry?.detail || "Healthy";

    card.innerHTML = `
      <div class="card-top">
        <div>
          <div class="card-kicker">
            <span class="phase-pill">${getPhaseLabel(check.phase)}</span>
            <span class="method-pill">${check.method}</span>
          </div>
          <h3>${check.name}</h3>
          <p class="card-description">${check.description}</p>
          <a class="url" href="${check.url}" target="_blank" rel="noreferrer">${check.url}</a>
        </div>
        <div class="status-tile ${getStatusClass(latestOk)}">
          <span class="status-label">${latestOk ? "Healthy" : "Degraded"}</span>
          <strong>${latestStatus}</strong>
          <span>${formatMs(latestEntry?.ms)}</span>
        </div>
      </div>
    `;

    const stats = document.createElement("div");
    stats.className = "stats";
    for (const window of windows) {
      const summary = data.summary[check.name][window];
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "stat-button";
      btn.innerHTML = `
        <div class="label">${window}</div>
        <div class="value">${summary.uptimePercent === null ? "—" : `${summary.uptimePercent.toFixed(3)}%`}</div>
        <div class="detail">${summary.failures} failures</div>
        <div class="detail">p95 ${formatMs(summary.p95Ms)}</div>
      `;
      stats.appendChild(btn);
      buttons.set(window, btn);
    }
    card.appendChild(stats);

    const metricsEl = document.createElement("div");
    metricsEl.className = "metrics";
    card.appendChild(metricsEl);

    const canvasWrap = document.createElement("div");
    canvasWrap.className = "chart-wrap";
    const canvas = document.createElement("canvas");
    canvasWrap.appendChild(canvas);
    card.appendChild(canvasWrap);

    const diagnostics = document.createElement("div");
    diagnostics.className = "diagnostics";
    card.appendChild(diagnostics);

    const ctx = canvas.getContext("2d");
    const failureLinePlugin = {
      id: "failureLines",
      afterDatasetsDraw(chart) {
        if (!failureRanges.length) return;
        const xScale = chart.scales.x;
        const yScale = chart.scales.y;
        if (!xScale || !yScale) return;
        const { ctx } = chart;
        ctx.save();
        for (const range of failureRanges) {
          const xStart = xScale.getPixelForValue(range.start);
          const xEnd = xScale.getPixelForValue(range.end);
          if (!Number.isFinite(xStart) || !Number.isFinite(xEnd) || xEnd <= xStart) continue;
          const gradient = ctx.createLinearGradient(xStart, 0, xEnd, 0);
          gradient.addColorStop(0, "rgba(220, 53, 69, 0)");
          gradient.addColorStop(0.5, "rgba(220, 53, 69, 0.18)");
          gradient.addColorStop(1, "rgba(220, 53, 69, 0)");
          ctx.fillStyle = gradient;
          ctx.fillRect(xStart, yScale.top, xEnd - xStart, yScale.bottom - yScale.top);
        }
        ctx.restore();
      },
    };

    const chart = new Chart(ctx, {
      type: "line",
      data: {
        datasets: [
          {
            label: "Response time (ms)",
            data: [],
            fill: false,
            tension: 0.2,
            pointRadius: 0,
            spanGaps: false,
            borderWidth: 1.5,
            borderColor: "#198754",
          },
        ],
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        layout: {
          padding: {
            left: 0,
            right: 0,
            top: 0,
            bottom: 0,
          },
        },
        scales: {
          x: {
            type: "time",
            time: { tooltipFormat: "yyyy-MM-dd HH:mm:ss" },
            ticks: {
              maxRotation: 0,
              autoSkipPadding: 10,
            },
            grid: {
              display: false,
            },
          },
          y: {
            beginAtZero: true,
            title: { display: true, text: "ms" },
            ticks: {
              padding: 6,
            },
          },
        },
        plugins: {
          legend: { display: false },
        },
      },
      plugins: [failureLinePlugin],
    });

    function updateMetrics(entriesSubset) {
      const statsValues = computeResponseStats(entriesSubset, data.slowThresholdMs);
      const failures = entriesSubset.filter((entry) => !entry.ok).length;
      const streak = [...entriesSubset].reverse().findIndex((entry) => entry.ok);
      const currentFailureStreak =
        failures === 0 ? 0 : streak === -1 ? entriesSubset.length : streak;
      metricsEl.innerHTML = "";
      const metrics = [
        ["Mean", formatMs(statsValues.mean), ""],
        ["Median", formatMs(statsValues.median), ""],
        ["P95", formatMs(statsValues.p95), ""],
        ["Failures", `${failures}/${entriesSubset.length}`, failures ? "bad" : ""],
        ["Fail streak", `${Math.max(0, currentFailureStreak)}`, currentFailureStreak ? "bad" : ""],
      ];

      for (const [label, value, extraClass] of metrics) {
        const metric = document.createElement("div");
        metric.className = `metric ${extraClass}`.trim();
        metric.innerHTML = `
          <span class="metric-label">${label}</span>
          <span class="metric-value">${value}</span>
        `;
        metricsEl.appendChild(metric);
      }
    }

    function updateDiagnostics(entriesSubset) {
      const windowLatest = entriesSubset.at(-1) || latestEntry;
      diagnostics.innerHTML = `
        <div class="diag-card">
          <div class="diag-title">Latest sample</div>
          <div class="diag-grid">
            <div><span class="diag-label">Checked</span><span>${formatTimestamp(windowLatest?.t)}</span></div>
            <div><span class="diag-label">Result</span><span>${windowLatest?.ok ? "Healthy" : "Degraded"}</span></div>
            <div><span class="diag-label">Reason</span><span>${windowLatest?.assertion || windowLatest?.detail || "Healthy"}</span></div>
            <div><span class="diag-label">Status</span><span>${windowLatest?.status ? `HTTP ${windowLatest.status}` : "—"}</span></div>
            <div><span class="diag-label">Last success</span><span>${formatTimeAgo(latest.lastSuccess?.t)}</span></div>
            <div><span class="diag-label">Last failure</span><span>${formatTimeAgo(latest.lastFailure?.t)}</span></div>
          </div>
        </div>
        <div class="diag-card">
          <div class="diag-title">Diagnostic headers</div>
          <div class="header-list">${renderHeaders(windowLatest?.headers || {})}</div>
          ${
            windowLatest?.bodySample
              ? `<div class="body-sample"><span class="diag-label">Body sample</span><code>${windowLatest.bodySample}</code></div>`
              : ""
          }
        </div>
        <div class="diag-card">
          <div class="diag-title">Recent failures</div>
          <div class="failure-list">${renderRecentFailures(entriesSubset)}</div>
        </div>
      `;
    }

    function applyWindow(window) {
      const duration = parseDuration(window);
      const now = Date.now();
      const subset = Number.isFinite(duration)
        ? entries.filter((entry) => now - entry.date.getTime() <= duration)
        : entries;
      const points = subset.map((entry) =>
        entry.ok ? { x: entry.date, y: entry.ms } : { x: entry.date, y: null },
      );
      failureRanges = computeFailureRangesForSubset(subset);
      chart.data.datasets[0].data = points;
      chart.update();

      buttons.forEach((button, key) => {
        button.classList.toggle("active", key === window);
      });
      updateMetrics(subset);
      updateDiagnostics(subset);
    }

    buttons.forEach((button, window) => {
      button.addEventListener("click", () => applyWindow(window));
    });

    const defaultWindow = windows.includes("24h") ? "24h" : windows[0];
    if (defaultWindow) applyWindow(defaultWindow);

    const phaseSection = phaseSections.get(check.phase);
    phaseSection.querySelector(".phase-grid").appendChild(card);
  }
}

document.addEventListener("DOMContentLoaded", main);
