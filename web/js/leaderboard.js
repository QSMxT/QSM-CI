// Leaderboard: fetch results/index.json and render a sortable, filterable table.
// Columns are driven by the track (the sim track exposes the full metric suite).

const METRIC_COLUMNS = {
  sim: [
    { key: "nrmse", label: "NRMSE %", better: "lower" },
    { key: "nrmse_detrend", label: "Detrend %", better: "lower" },
    { key: "nrmse_tissue", label: "Tissue %", better: "lower" },
    { key: "nrmse_blood", label: "Blood %", better: "lower" },
    { key: "nrmse_dgm", label: "DGM %", better: "lower" },
    { key: "dgm_linearity", label: "DGM lin.", better: "lower" },
    { key: "calc_streak", label: "Streak", better: "lower" },
    { key: "correlation", label: "r", better: "higher" },
    { key: "xsim", label: "XSIM", better: "higher" },
    { key: "runtime_s", label: "Time (s)", better: "lower" },
  ],
  invivo: [
    { key: "correlation", label: "r", better: "higher" },
    { key: "xsim", label: "XSIM", better: "higher" },
    { key: "runtime_s", label: "Time (s)", better: "lower" },
  ],
};

const state = { runs: [], track: "sim", sortKey: "xsim", sortDir: "desc", filter: "" };

async function load() {
  const res = await fetch("results/index.json");
  const data = await res.json();
  state.runs = data.runs || [];
  render();
}

function activeColumns() {
  return METRIC_COLUMNS[state.track] || METRIC_COLUMNS.sim;
}

function visibleRuns() {
  const f = state.filter.toLowerCase();
  return state.runs
    .filter((r) => r.track === state.track)
    .filter((r) => !f || `${r.name} ${(r.authors || []).join(" ")}`.toLowerCase().includes(f))
    .sort((a, b) => {
      const av = a.metrics?.[state.sortKey] ?? a[state.sortKey];
      const bv = b.metrics?.[state.sortKey] ?? b[state.sortKey];
      if (av == null) return 1;
      if (bv == null) return -1;
      return state.sortDir === "asc" ? av - bv : bv - av;
    });
}

function render() {
  const cols = activeColumns();
  const headerRow = document.getElementById("header-row");
  headerRow.innerHTML =
    `<th class="name-col">Algorithm</th>` +
    cols.map((c) => `<th data-key="${c.key}" class="sortable">${c.label}` +
      (state.sortKey === c.key ? (state.sortDir === "asc" ? " ▲" : " ▼") : "") + `</th>`).join("");
  headerRow.querySelectorAll("th.sortable").forEach((th) =>
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      if (state.sortKey === key) state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      else { state.sortKey = key; state.sortDir = "desc"; }
      render();
    })
  );

  const runs = visibleRuns();
  const tbody = document.getElementById("rows");
  tbody.innerHTML = runs.map((r) => {
    const cells = cols.map((c) => {
      const v = r.metrics?.[c.key] ?? r[c.key];
      return `<td>${v == null ? "—" : Number(v).toFixed(c.key === "correlation" || c.key === "xsim" || c.key === "dgm_linearity" ? 4 : 2)}</td>`;
    }).join("");
    return `<tr onclick="location.href='submission.html?run=${encodeURIComponent(r.id)}'">` +
      `<td class="name-col"><strong>${r.name}</strong>` +
      `<span class="authors">${(r.authors || []).join(", ")}</span></td>${cells}</tr>`;
  }).join("");

  document.getElementById("empty").hidden = runs.length > 0;
}

document.getElementById("track").addEventListener("change", (e) => {
  state.track = e.target.value;
  const cols = activeColumns();
  if (!cols.some((c) => c.key === state.sortKey)) state.sortKey = cols[cols.length - 2].key;
  render();
});
document.getElementById("filter").addEventListener("input", (e) => {
  state.filter = e.target.value;
  render();
});

load();
