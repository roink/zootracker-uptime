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
    .filter(e => e.ok)
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
  const titleEl = document.querySelector("#title");
  const img = titleEl.querySelector("img");
  titleEl.textContent = data.siteName || "Uptime";
  if (img) titleEl.prepend(img);
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
    let failedTimes = [];
    let failureRanges = [];

    const ctx = canvas.getContext("2d");
    const failureLinePlugin = {
      id: "failureLines",
      // Draw semi-transparent red stripes over failure ranges.
      afterDatasetsDraw(chart) {
        if (!failureRanges.length) return;
    
        const xScale = chart.scales.x;
        const yScale = chart.scales.y;
        if (!xScale || !yScale) return;
    
        const minVisible = xScale.min;
        const maxVisible = xScale.max;
        const { ctx } = chart;
    
        ctx.save();
    
        failureRanges.forEach(range => {
          const startT = range.start.getTime();
          const endT = range.end.getTime();
    
          // Skip if completely outside current view
          if (endT < minVisible || startT > maxVisible) return;
    
          // Clamp to visible window
          const clampedStart = new Date(Math.max(startT, minVisible));
          const clampedEnd = new Date(Math.min(endT, maxVisible));
    
          const xStart = xScale.getPixelForValue(clampedStart);
          const xEnd = xScale.getPixelForValue(clampedEnd);
          const width = xEnd - xStart;
          if (width <= 0) return;
    
          const top = yScale.top;
          const bottom = yScale.bottom;
          const height = bottom - top;
    
          // Nice gradient / soft edges (sort of "gamma" look)
          const gradient = ctx.createLinearGradient(xStart, 0, xEnd, 0);
          gradient.addColorStop(0.0, "rgba(255, 0, 0, 0.0)");
          gradient.addColorStop(0.2, "rgba(255, 0, 0, 0.10)");
          gradient.addColorStop(0.5, "rgba(255, 0, 0, 0.18)");
          gradient.addColorStop(0.8, "rgba(255, 0, 0, 0.10)");
          gradient.addColorStop(1.0, "rgba(255, 0, 0, 0.0)");
    
          ctx.fillStyle = gradient;
          ctx.fillRect(xStart, top, width, height);
    
          // Optional subtle border (can be removed if you don’t like it)
          ctx.strokeStyle = "rgba(255, 0, 0, 0.3)";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(xStart, top);
          ctx.lineTo(xStart, bottom);
          ctx.moveTo(xEnd, top);
          ctx.lineTo(xEnd, bottom);
          ctx.stroke();
        });
    
        ctx.restore();
      }
    };
    function computeFailureRangesForSubset(subset) {
      const ranges = [];
      if (!subset.length) return ranges;
    
      let i = 0;
      while (i < subset.length) {
        if (subset[i].ok) {
          i++;
          continue;
        }
    
        // Start of a consecutive failure block
        const startIndex = i;
        while (i + 1 < subset.length && !subset[i + 1].ok) {
          i++;
        }
        const endIndex = i;
    
        const firstFail = subset[startIndex].date;
        const lastFail = subset[endIndex].date;
        const prev = startIndex > 0 ? subset[startIndex - 1].date : null;
        const next = endIndex < subset.length - 1 ? subset[endIndex + 1].date : null;
    
        let startTime;
        let endTime;
    
        if (prev && next) {
          // Normal case: failures between two successful checks
          startTime = new Date((prev.getTime() + firstFail.getTime()) / 2);
          endTime = new Date((next.getTime() + lastFail.getTime()) / 2);
        } else if (prev && !next) {
          // Failures at the right edge of the window
          const leftMid = (prev.getTime() + firstFail.getTime()) / 2;
          const extra = lastFail.getTime() - prev.getTime();
          startTime = new Date(leftMid);
          endTime = new Date(lastFail.getTime() + extra / 2);
        } else if (!prev && next) {
          // Failures at the left edge of the window
          const rightMid = (next.getTime() + lastFail.getTime()) / 2;
          const extra = next.getTime() - firstFail.getTime();
          startTime = new Date(firstFail.getTime() - extra / 2);
          endTime = new Date(rightMid);
        } else {
          // All entries in the window are failures
          startTime = new Date(firstFail.getTime());
          endTime = new Date(lastFail.getTime());
        }
    
        ranges.push({ start: startTime, end: endTime });
    
        i++;
      }
    
      return ranges;
    }

    const chart = new Chart(ctx, {
      type: "line",
      data: {
        datasets: [{
          label: "Response time (ms)",
          data: [],
          fill: false,
          tension: 0.2,
          pointRadius: 0,
          spanGaps: false,
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
      },
      plugins: [failureLinePlugin]
    });

    function updateMetrics(entriesSubset) {
      const statsValues = computeResponseStats(entriesSubset);
      const total = entriesSubset.length;
      const failures = entriesSubset.filter(e => !e.ok).length;
      const noSuccessful = statsValues.mean === null && total > 0;
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
        <div class="metric">
          <span class="metric-label">Failures</span>
          <span class="metric-value">${failures} / ${total}</span>
        </div>
        ${noSuccessful ? "<div class=\"metric note\"><span class=\"metric-label\">Note</span><span class=\"metric-value\">No successful checks in window</span></div>" : ""}
      `;
    }

    function applyWindow(windowKey) {
      const duration = parseDuration(windowKey);
      const now = Date.now();
      const subset = !isFinite(duration)
        ? entries
        : entries.filter(e => now - e.date.getTime() <= duration);
    
      // Keep timestamps around if you still want them, but they’re not
      // needed for drawing anymore:
      failedTimes = subset.filter(e => !e.ok).map(e => e.date);
    
      // New: compute failure ranges for the plugin
      failureRanges = computeFailureRangesForSubset(subset);
    
      const points = subset.map(p =>
        p.ok ? { x: p.date, y: p.ms } : { x: p.date, y: null }
      );
    
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
        <div class="detail">avg ${formatMs(s.avgMs)}</div>
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

