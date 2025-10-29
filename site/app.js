async function main() {
  const data = await fetch("./data/data.json", { cache: "no-store" }).then(r => r.json());
  document.querySelector("#title").textContent = data.siteName || "Uptime";
  document.querySelector("#last-run").textContent = `Last run (UTC): ${new Date(data.lastRunUTC).toISOString()}`;

  const container = document.querySelector("#checks");
  for (const c of data.checks) {
    const wrap = document.createElement("section");
    wrap.className = "card";

    const h2 = document.createElement("h2");
    h2.innerHTML = `<span>${c.name}</span> <a class="url" href="${c.url}" target="_blank" rel="noreferrer">${c.url}</a>`;
    wrap.appendChild(h2);

    const stats = document.createElement("div");
    stats.className = "stats";
    const windows = ["24h","7d","30d","365d","all"].filter(w => data.summary[c.name][w] !== undefined);
    for (const w of windows) {
      const s = data.summary[c.name][w];
      const el = document.createElement("div");
      el.className = "stat";
      const badgeClass = s.uptimePercent === null ? "" : s.uptimePercent === 100 ? "up badge" : (s.uptimePercent >= 99.9 ? "up badge" : "down badge");
      el.innerHTML = `
        <div class="label">${w}</div>
        <div class="value">${s.uptimePercent === null ? "—" : s.uptimePercent.toFixed(3) + "%"}</div>
        <div class="${badgeClass}">${s.total} checks</div>
      `;
      stats.appendChild(el);
    }
    wrap.appendChild(stats);

    const canvas = document.createElement("canvas");
    wrap.appendChild(canvas);

    // Build chart dataset
    const series = data.series[c.name] || [];
    const points = series.map(p => ({ x: new Date(p.t), y: p.ms }));

    const ctx = canvas.getContext("2d");
    new Chart(ctx, {
      type: "line",
      data: {
        datasets: [{
          label: "Response time (ms)",
          data: points,
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

    container.appendChild(wrap);
  }
}

document.addEventListener("DOMContentLoaded", main);

