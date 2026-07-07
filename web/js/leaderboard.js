// Leaderboard for the v2 staged schema.
//   - Per-stage (isolated): each stage's submissions scored against their GT boundary.
//   - Combinations (composed): the BFR × dipole matrix, as a sortable table and a heatmap.
// Columns are derived from the metrics actually present (field stages expose fewer than chi).

const PREFERRED = [
  "nrmse", "nrmse_detrend", "nrmse_tissue", "nrmse_blood", "nrmse_dgm",
  "dgm_linearity", "calc_moment_dev", "calc_streak", "correlation", "xsim",
];
const LOWER_BETTER = new Set([
  "nrmse", "nrmse_detrend", "nrmse_tissue", "nrmse_blood", "nrmse_dgm",
  "dgm_linearity", "calc_moment_dev", "calc_streak", "runtime_s",
]);
const DP = (k) => (["correlation", "xsim", "dgm_linearity"].includes(k) ? 4 : 2);

const state = { runs: [], view: "isolated", stage: "dipole", fmap: "gt", metric: "xsim", sortKey: "xsim", sortDir: "desc", filter: "" };

async function load() {
  state.runs = (await (await fetch("results/index.json")).json()).runs || [];
  const stages = [...new Set(state.runs.filter((r) => r.mode === "isolated").map((r) => r.stage))];
  if (!stages.includes(state.stage)) state.stage = stages[0] || "dipole";
  render();
}

function isolatedRuns() {
  return state.runs.filter((r) => r.mode === "isolated" && r.stage === state.stage);
}
function fieldMappings() {
  return [...new Set(state.runs.filter((r) => r.mode === "composed" && r.combo).map((r) => r.combo.field_mapping || "gt"))];
}
function composedRuns() {
  // Show pipelines for the selected field-mapping source, plus spans (no combo).
  return state.runs.filter((r) => r.mode === "composed" &&
    (!r.combo || (r.combo.field_mapping || "gt") === state.fmap));
}

function metricKeys(runs) {
  const present = new Set();
  runs.forEach((r) => Object.entries(r.metrics || {}).forEach(([k, v]) => v != null && present.add(k)));
  return PREFERRED.filter((k) => present.has(k)).concat(runs.some((r) => r.runtime_s != null) ? ["runtime_s"] : []);
}

function val(r, k) { return r.metrics?.[k] ?? r[k]; }

function renderControls(cols) {
  const stages = [...new Set(state.runs.filter((r) => r.mode === "isolated").map((r) => r.stage))];
  const el = document.getElementById("controls");
  el.innerHTML = `
    <label>View:
      <select id="view">
        <option value="isolated"${state.view === "isolated" ? " selected" : ""}>Per-stage (isolated)</option>
        <option value="composed"${state.view === "composed" ? " selected" : ""}>Combinations (composed)</option>
      </select></label>
    ${state.view === "isolated" ? `<label>Stage:
      <select id="stage">${stages.map((s) => `<option${s === state.stage ? " selected" : ""}>${s}</option>`).join("")}</select></label>` : ""}
    ${state.view === "composed" && fieldMappings().length > 1 ? `<label>Field mapping:
      <select id="fmap">${fieldMappings().map((f) => `<option${f === state.fmap ? " selected" : ""}>${f}</option>`).join("")}</select></label>` : ""}
    ${state.view === "composed" ? `<label>Matrix metric:
      <select id="metric">${cols.filter((c) => c !== "runtime_s").map((c) => `<option${c === state.metric ? " selected" : ""}>${c}</option>`).join("")}</select></label>` : ""}
    <input id="filter" type="search" placeholder="Filter…" value="${state.filter}" />`;
  el.querySelector("#view").onchange = (e) => { state.view = e.target.value; render(); };
  if (el.querySelector("#stage")) el.querySelector("#stage").onchange = (e) => { state.stage = e.target.value; render(); };
  if (el.querySelector("#fmap")) el.querySelector("#fmap").onchange = (e) => { state.fmap = e.target.value; render(); };
  if (el.querySelector("#metric")) el.querySelector("#metric").onchange = (e) => { state.metric = e.target.value; renderMatrix(); };
  el.querySelector("#filter").oninput = (e) => { state.filter = e.target.value; render(); };
}

function renderTable(runs, cols) {
  const f = state.filter.toLowerCase();
  const rows = runs
    .filter((r) => !f || r.name.toLowerCase().includes(f))
    .sort((a, b) => {
      const av = val(a, state.sortKey), bv = val(b, state.sortKey);
      if (av == null) return 1; if (bv == null) return -1;
      return state.sortDir === "asc" ? av - bv : bv - av;
    });
  const head = `<tr><th class="name-col">${state.view === "composed" ? "BFR + dipole" : "Algorithm"}</th>` +
    cols.map((c) => `<th data-key="${c}" class="sortable">${c}${state.sortKey === c ? (state.sortDir === "asc" ? " ▲" : " ▼") : ""}</th>`).join("") + "</tr>";
  const body = rows.map((r) => `<tr onclick="location.href='submission.html?run=${encodeURIComponent(r.id)}'">` +
    `<td class="name-col"><strong>${r.name}</strong></td>` +
    cols.map((c) => { const v = val(r, c); return `<td>${v == null ? "—" : Number(v).toFixed(DP(c))}</td>`; }).join("") + "</tr>").join("");
  const t = document.getElementById("table");
  t.innerHTML = `<thead>${head}</thead><tbody>${body}</tbody>`;
  t.querySelectorAll("th.sortable").forEach((th) => th.onclick = () => {
    const k = th.dataset.key;
    if (state.sortKey === k) state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
    else { state.sortKey = k; state.sortDir = LOWER_BETTER.has(k) ? "asc" : "desc"; }
    render();
  });
}

function renderMatrix() {
  const runs = composedRuns().filter((r) => r.combo);
  const bfrs = [...new Set(runs.map((r) => r.combo.bfr))];
  const dips = [...new Set(runs.map((r) => r.combo.dipole))];
  const cell = {}; runs.forEach((r) => { cell[`${r.combo.bfr}|${r.combo.dipole}`] = r; });
  const vals = runs.map((r) => val(r, state.metric)).filter((v) => v != null);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const lower = LOWER_BETTER.has(state.metric);
  const color = (v) => {
    if (v == null) return "transparent";
    let t = hi === lo ? 0.5 : (v - lo) / (hi - lo);
    if (lower) t = 1 - t;                          // green = better
    return `hsl(${Math.round(t * 130)} 60% 30%)`;  // red→green
  };
  const head = `<tr><th>BFR ↓ / dipole →</th>${dips.map((d) => `<th>${d}</th>`).join("")}</tr>`;
  const body = bfrs.map((b) => `<tr><th class="name-col">${b}</th>` + dips.map((d) => {
    const r = cell[`${b}|${d}`]; const v = r ? val(r, state.metric) : null;
    return `<td class="cell" style="background:${color(v)}"${r ? ` onclick="location.href='submission.html?run=${encodeURIComponent(r.id)}'"` : ""}>` +
      `${v == null ? "—" : Number(v).toFixed(DP(state.metric))}</td>`;
  }).join("") + "</tr>").join("");
  const fmNote = state.fmap === "gt" ? "ground-truth field" : `field mapping: ${state.fmap}`;
  document.getElementById("matrix").innerHTML =
    `<h3>Combination matrix — ${state.metric} <span class="hint">(${fmNote}; greener = better)</span></h3>` +
    `<table class="heatmap">${head}${body}</table>`;
}

function render() {
  const fms = fieldMappings();
  if (fms.length && !fms.includes(state.fmap)) state.fmap = fms.includes("gt") ? "gt" : fms[0];
  const runs = state.view === "isolated" ? isolatedRuns() : composedRuns();
  const cols = metricKeys(runs);
  if (!cols.includes(state.sortKey)) state.sortKey = "xsim";
  if (!cols.includes(state.metric)) state.metric = cols.includes("xsim") ? "xsim" : cols[0];
  renderControls(cols);
  document.getElementById("matrix").innerHTML = "";
  if (state.view === "composed") renderMatrix();
  renderTable(runs, cols);
  document.getElementById("empty").hidden = runs.length > 0;
}

load();
