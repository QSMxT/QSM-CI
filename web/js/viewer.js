// Submission detail + NiiVue viewer with a run sidebar and in-place switching.
// Module scope (needs `import`); shared helpers via window.QSM.
import { Niivue } from "https://unpkg.com/@niivue/niivue@0.57.0/dist/index.js";

const { loadRuns, METRICS, STAGE_LABEL, val, fmt } = window.QSM;

const STAGE_COLOR = {
  "field-mapping": "bg-indigo-50 text-indigo-700 ring-indigo-100",
  bfr: "bg-violet-50 text-violet-700 ring-violet-100",
  dipole: "bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-100",
};

let allRuns = [];
let nv = null;        // created lazily on the first run that has volumes
let run;              // current run
let baseUrl, win, filter = "";

const $ = (id) => document.getElementById(id);
function badge(text, cls) {
  return `<span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${cls}">${text}</span>`;
}

// ---- sidebar ----------------------------------------------------------------

function sidebarGroups() {
  const iso = (stage) => allRuns.filter((r) => r.mode === "isolated" && r.stage === stage);
  const fmaps = [...new Set(allRuns.filter((r) => r.mode === "composed" && r.combo).map((r) => r.combo.field_mapping || "gt"))];
  const groups = [];
  for (const s of ["dipole", "bfr", "field-mapping"]) {
    const rs = iso(s); if (rs.length) groups.push({ header: STAGE_LABEL[s] || s, runs: rs });
  }
  for (const f of fmaps) {
    const rs = allRuns.filter((r) => r.mode === "composed" && (r.combo?.field_mapping || "gt") === f);
    if (rs.length) groups.push({ header: "Pipelines · " + (f === "gt" ? "GT field" : f), runs: rs });
  }
  return groups;
}

function buildSidebar() {
  const f = filter.toLowerCase();
  const html = sidebarGroups().map((g) => {
    const items = g.runs.filter((r) => !f || r.name.toLowerCase().includes(f));
    if (!items.length) return "";
    const rows = items.map((r) => {
      const active = r.id === run?.id;
      const primary = val(r, "xsim");
      const right = r.status === "DNF" ? "DNF" : (primary != null ? fmt(primary, "xsim") : "");
      return `<button data-id="${r.id}"
        class="run-item w-full text-left rounded-lg px-2.5 py-1.5 text-sm flex items-center justify-between gap-2 transition
               ${active ? "bg-indigo-50 text-indigo-700 font-medium" : "text-gray-600 hover:bg-gray-50"}">
        <span class="truncate">${r.name}</span>
        <span class="shrink-0 tabular-nums text-xs ${r.status === "DNF" ? "text-gray-300" : active ? "text-indigo-500" : "text-gray-400"}">${right}</span>
      </button>`;
    }).join("");
    return `<div class="mb-2">
      <div class="px-2.5 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">${g.header}</div>
      ${rows}</div>`;
  }).join("");
  $("run-list").innerHTML = html || `<p class="p-3 text-sm text-gray-400">No matches.</p>`;
  $("run-list").querySelectorAll(".run-item").forEach((b) =>
    b.addEventListener("click", () => selectRun(b.dataset.id)));
}

function selectRun(id) {
  run = allRuns.find((r) => r.id === id);
  history.replaceState(null, "", "?run=" + encodeURIComponent(id));
  buildSidebar();
  loadRun();
}

// ---- detail + viewer --------------------------------------------------------

async function loadRun() {
  $("sub-title").textContent = run.name;
  const stageCls = STAGE_COLOR[run.stage] || "bg-gray-100 text-gray-600 ring-gray-200";
  $("sub-badges").innerHTML =
    badge(STAGE_LABEL[run.stage] || run.stage, stageCls) +
    badge(run.mode === "composed" ? "Composed pipeline" : "Isolated", "bg-gray-100 text-gray-600 ring-gray-200") +
    (run.status === "DNF" ? badge("DNF", "bg-red-50 text-red-600 ring-red-100") : "");
  const bits = [];
  if (run.artifact) bits.push(`scored artifact <code class="text-gray-700">${run.artifact}</code>`);
  if (run.runtime_s != null) bits.push(`runtime ${run.runtime_s.toFixed(1)}s`);
  if (run.image) bits.push(`image <code class="text-gray-700">${run.image}</code>`);
  $("sub-meta").innerHTML = bits.join(" · ");
  renderMetrics();

  const note = $("viewer-note"), canvas = $("gl1"), tabs = $("layer-tabs");
  if (run.status === "DNF") {
    canvas.style.visibility = "hidden"; tabs.style.visibility = "hidden";
    note.textContent = "This run did not produce a valid output (DNF).";
    note.classList.remove("hidden"); note.classList.add("flex");
    return;
  }
  canvas.style.visibility = "visible"; tabs.style.visibility = "visible";
  note.classList.add("hidden"); note.classList.remove("flex");

  baseUrl = `results/${run.id}/`;
  win = run.kind === "field"
    ? { lo: -1.0, hi: 1.0, elo: 0, ehi: 0.5 }
    : { lo: -0.1, hi: 0.1, elo: 0, ehi: 0.05 };

  if (!nv) {
    nv = new Niivue({
      isColorbar: true, textHeight: 0.03, show3Dcrosshair: false, crosshairWidth: 0.75,
      backColor: [0, 0, 0, 1],
      onLocationChange: (d) => { $("intensity").innerHTML = d.string; },
    });
    await nv.attachTo("gl1");
    nv.setSliceType(nv.sliceTypeMultiplanar);
    wireControls();
  }
  setLayerActive("recon");
  try { await showLayer("recon"); } catch (e) {
    canvas.style.visibility = "hidden";
    note.textContent = "Interactive volumes aren't available for this run.";
    note.classList.remove("hidden"); note.classList.add("flex");
  }
}

function renderMetrics() {
  const m = run.metrics || {};
  $("metrics-sub").textContent =
    run.mode === "composed" ? "Final χ map vs. ground truth" : `${run.artifact || "output"} vs. ground truth`;
  const order = Object.keys(METRICS).filter((k) => m[k] != null);
  $("metrics-body").innerHTML = order.map((k) => {
    const meta = METRICS[k];
    const arrow = meta.better === "higher" ? "↑" : "↓";
    const hero = k === "xsim" || k === "nrmse";
    return `<tr>
      <td class="py-2.5 text-gray-500">${meta.label} <span class="text-gray-300" title="${meta.better} is better">${arrow}</span></td>
      <td class="py-2.5 text-right tabular-nums ${hero ? "font-bold text-gray-900" : "font-medium text-gray-700"}">${fmt(m[k], k)}</td>
    </tr>`;
  }).join("") || `<tr><td class="py-3 text-gray-400">No metrics for this run.</td></tr>`;
}

function setLayerActive(layer) {
  $("layer-tabs").querySelectorAll("button").forEach((t) =>
    t.className = "rounded-md px-3 py-1 transition " +
      (t.dataset.layer === layer ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"));
}
function wireControls() {
  $("layer-tabs").querySelectorAll("button").forEach((t) =>
    t.addEventListener("click", () => { setLayerActive(t.dataset.layer); showLayer(t.dataset.layer); }));
  $("opacity").addEventListener("input", (e) => {
    for (let i = 1; i < nv.volumes.length; i++) nv.setOpacity(i, parseFloat(e.target.value));
    nv.updateGLVolume();
  });
}

async function showLayer(layer) {
  const opacity = parseFloat($("opacity").value);
  if (layer === "error") {
    await nv.loadVolumes([{ url: baseUrl + "truth.nii.gz", colormap: "gray" }]);
    nv.volumes[0].cal_min = win.lo; nv.volumes[0].cal_max = win.hi;
    await nv.addVolumeFromUrl({ url: baseUrl + "error.nii.gz", colormap: "warm", opacity });
    const ov = nv.volumes[nv.volumes.length - 1];
    ov.cal_min = win.elo; ov.cal_max = win.ehi;
  } else {
    await nv.loadVolumes([{ url: baseUrl + (layer === "truth" ? "truth.nii.gz" : "recon.nii.gz"), colormap: "gray" }]);
    nv.volumes[0].cal_min = win.lo; nv.volumes[0].cal_max = win.hi;
  }
  nv.updateGLVolume();
}

// ---- boot -------------------------------------------------------------------

async function init() {
  allRuns = await loadRuns();
  const id = new URLSearchParams(location.search).get("run");
  run = allRuns.find((r) => r.id === id) || allRuns.find((r) => r.status !== "DNF") || allRuns[0];
  if (!run) { $("sub-title").textContent = "No runs"; return; }
  $("run-filter").addEventListener("input", (e) => { filter = e.target.value; buildSidebar(); });
  buildSidebar();
  loadRun();
}

init();
