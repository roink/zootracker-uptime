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
  return value === null ? "—" : `${value} ms`;
}

function computeResponseStats(entries) {
  const values = entries
    .map(e => e.ms)
    .filter(v => typeof v === "number" && Number.isFinite(v));
  if (!values.length) {
    return { mean: null, median: null, p95: null };
  }

  const sorted = [...values].sort((a, b) => a - b);
  const total = values.reduce((sum, v) => sum + v, 0);
  const mean = Math.round(total / values.length);
  const mid = Math.floor(sorted.length / 2);
  const median =
    sorted.length % 2 === 0
      ? Math.round((sorted[mid - 1] + sorted[mid]) / 2)
      : sorted[mid];
  const p95Index = Math.floor(0.95 * (sorted.length - 1));
  const p95 = sorted[p95Index];

  return { mean, median, p95 };
}

function formatLastUpdated(dateString) {
  const lastRun = new Date(dateString);
  const diffMs = Date.now() - lastRun.getTime();
  const minutes = Math.max(0, Math.round(diffMs / 60000));
  const unit = minutes === 1 ? "minute" : "minutes";
  return `Last updated ${minutes} ${unit} ago`;
}

async function main() {
  const data = await fetch("./data/data.json", { cache: "no-store" }).then(r => r.json());
  document.querySelector("#title").textContent = data.siteName || "Uptime";
  document.querySelector("#last-run").textContent = formatLastUpdated(data.lastRunUTC);

  const container = document.querySelector("#checks");
  for (const c of data.checks) {
    const wrap = document.createElement("section");
    wrap.className = "card";

    const h2 = document.createElement("h2");
    h2.innerHTML = `<span>${c.name}</span> <a class="url" href="${c.url}" target="_blank" rel="noreferrer">${c.url}</a>`;
    wrap.appendChild(h2);

    const stats = document.createElement("div");
    stats.className = "stats";
    const metricsEl = document.createElement("div");
    metricsEl.className = "metrics";

    const canvas = document.createElement("canvas");

    const entries = (data.series[c.name] || []).map(entry => ({ ...entry, date: new Date(entry.t) }));
    const windows = ["24h", "7d", "30d", "365d", "all"].filter(w => data.summary[c.name][w] !== undefined);
    const buttons = new Map();

    const ctx = canvas.getContext("2d");
    const chart = new Chart(ctx, {
      type: "line",
      data: {
        datasets: [{
          label: "Response time (ms)",
          data: [],
          fill: false,
          tension: 0.2,
          pointRadius: 0,
          borderWidth: 1.5
        }]
      },
      options: {
        animation: false,
        responsive: true,
        scales: {
          x: { type: "time", time: { tooltipFormat: "yyyy-MM-dd HH:mm:ss" } },
          y: { beginAtZero: true, title: { display: true, text: "ms" } }
        },
        plugins: {
          legend: { display: true }
        }
      }
    });

    function updateMetrics(entriesSubset) {
      const statsValues = computeResponseStats(entriesSubset);
      metricsEl.innerHTML = `
        <div class="metric">
          <span class="metric-label">Mean</span>
          <span class="metric-value">${formatMs(statsValues.mean)}</span>
        </div>
        <div class="metric">
          <span class="metric-label">Median</span>
          <span class="metric-value">${formatMs(statsValues.median)}</span>
        </div>
        <div class="metric">
          <span class="metric-label">P95</span>
          <span class="metric-value">${formatMs(statsValues.p95)}</span>
        </div>
      `;
    }

    function applyWindow(windowKey) {
      const duration = parseDuration(windowKey);
      const now = Date.now();
      const subset = !isFinite(duration)
        ? entries
        : entries.filter(e => now - e.date.getTime() <= duration);
      const points = subset.map(p => ({ x: p.date, y: p.ms }));
      chart.data.datasets[0].data = points;
      chart.update();
      buttons.forEach((btn, key) => {
        btn.classList.toggle("active", key === windowKey);
      });
      updateMetrics(subset);
    }

    for (const w of windows) {
      const s = data.summary[c.name][w];
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "stat-button";
      const badgeClass = s.uptimePercent === null
        ? ""
        : s.uptimePercent === 100
        ? "up badge"
        : (s.uptimePercent >= 99.9 ? "up badge" : "down badge");
      btn.innerHTML = `
        <div class="label">${w}</div>
        <div class="value">${s.uptimePercent === null ? "—" : s.uptimePercent.toFixed(3) + "%"}</div>
        <div class="${badgeClass}">${s.total} checks</div>
      `;
      btn.addEventListener("click", () => applyWindow(w));
      stats.appendChild(btn);
      buttons.set(w, btn);
    }

    wrap.appendChild(stats);
    wrap.appendChild(metricsEl);
    wrap.appendChild(canvas);

    const defaultWindow = windows.includes("24h") ? "24h" : windows[0];
    if (defaultWindow) {
      applyWindow(defaultWindow);
    }

    container.appendChild(wrap);
  }
}

document.addEventListener("DOMContentLoaded", main);

