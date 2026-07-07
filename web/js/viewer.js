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
let baseUrl, win, filter = "", navMode = "stages";

const $ = (id) => document.getElementById(id);
function badge(text, cls) {
  return `<span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${cls}">${text}</span>`;
}

// ---- sidebar ----------------------------------------------------------------

const uniq = (arr) => [...new Set(arr)];
const composedRuns = () => allRuns.filter((r) => r.mode === "composed" && r.combo);
const fmapsList = () => {
  const s = uniq(composedRuns().map((r) => r.combo.field_mapping || "gt"));
  return s.includes("gt") ? ["gt", ...s.filter((x) => x !== "gt")] : s;  // ground truth first (default)
};
const bfrList = () => uniq(composedRuns().map((r) => r.combo.bfr));
const dipoleList = () => uniq(composedRuns().map((r) => r.combo.dipole));
const findPipeline = (f, b, d) => composedRuns().find((r) =>
  (r.combo.field_mapping || "gt") === f && r.combo.bfr === b && r.combo.dipole === d);

function currentCombo() {
  if (run?.combo) return { fmap: run.combo.field_mapping || "gt", bfr: run.combo.bfr, dipole: run.combo.dipole };
  const c = { fmap: fmapsList()[0], bfr: bfrList()[0], dipole: dipoleList()[0] };
  if (run?.mode === "isolated") { if (run.stage === "dipole") c.dipole = run.slug; if (run.stage === "bfr") c.bfr = run.slug; }
  return c;
}

function runItem(r, activeId) {
  const active = r && r.id === activeId;
  const label = r ? (r.status === "DNF" ? "DNF" : fmt(val(r, "xsim"), "xsim")) : "—";
  const dis = !r || r.status === "DNF";
  return `<button data-id="${r ? r.id : ""}" ${dis ? "" : ""}
    class="run-item w-full text-left rounded-lg px-2.5 py-1.5 text-sm flex items-center justify-between gap-2 transition
      ${active ? "bg-indigo-50 text-indigo-700 font-medium" : "text-gray-600 hover:bg-gray-50"} ${!r ? "opacity-40 cursor-default" : ""}">
    <span class="truncate">%NAME%</span>
    <span class="shrink-0 tabular-nums text-xs ${dis ? "text-gray-300" : active ? "text-indigo-500" : "text-gray-400"}">${label}</span>
  </button>`;
}

function stagesHTML() {
  const f = filter.toLowerCase();
  return ["dipole", "bfr", "field-mapping"].map((s) => {
    const rs = allRuns.filter((r) => r.mode === "isolated" && r.stage === s && (!f || r.name.toLowerCase().includes(f)));
    if (!rs.length) return "";
    const rows = rs.map((r) => runItem(r, run?.id).replace("%NAME%", r.name)).join("");
    return `<div class="mb-3"><div class="px-2.5 pt-1 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">${STAGE_LABEL[s] || s}</div>${rows}</div>`;
  }).join("") || `<p class="p-3 text-sm text-gray-400">No matches.</p>`;
}

const fmapName = (m) => (m === "gt" ? "ground truth" : m);

function pipelinesHTML() {
  if (!composedRuns().length)
    return `<p class="p-3 text-sm text-gray-400">No pipeline combinations available yet — the composed matrix is computed by the nightly job.</p>`;
  const cur = currentCombo();
  const f = filter.toLowerCase();
  const axis = (title, methods, kind) => {
    const rows = methods.filter((m) => {
      const nm = kind === "fmap" ? fmapName(m) : m;
      return !f || nm.toLowerCase().includes(f);
    }).map((m) => {
      const rn = kind === "fmap" ? findPipeline(m, cur.bfr, cur.dipole)
        : kind === "bfr" ? findPipeline(cur.fmap, m, cur.dipole)
        : findPipeline(cur.fmap, cur.bfr, m);
      return runItem(rn, run?.id).replace("%NAME%", kind === "fmap" ? fmapName(m) : m);
    }).join("");
    return `<div class="mb-3"><div class="px-2.5 pt-1 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">${title}</div>${rows}</div>`;
  };
  return axis("Field mapping", fmapsList(), "fmap")
    + axis("Background removal", bfrList(), "bfr")
    + axis("Dipole inversion", dipoleList(), "dipole");
}

function buildSidebar() {
  document.querySelectorAll("#nav-toggle button").forEach((b) =>
    b.className = "flex-1 rounded-md px-2 py-1 transition " +
      (b.dataset.mode === navMode ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"));
  $("run-list").innerHTML = navMode === "stages" ? stagesHTML() : pipelinesHTML();
  $("run-list").querySelectorAll(".run-item").forEach((b) =>
    b.addEventListener("click", () => { if (b.dataset.id) selectRun(b.dataset.id); }));
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

  const note = $("viewer-note"), canvas = $("gl1"), controls = $("viewer-controls");
  if (run.status === "DNF") {
    canvas.style.visibility = "hidden"; controls.style.display = "none";
    note.textContent = "This run did not produce a valid output (DNF).";
    note.classList.remove("hidden"); note.classList.add("flex");
    return;
  }
  canvas.style.visibility = "visible"; controls.style.display = "";
  note.classList.add("hidden"); note.classList.remove("flex");

  baseUrl = `results/${run.id}/`;

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
const cap = (s) => s[0].toUpperCase() + s.slice(1);
const baseVol = () => nv.volumes[0];
function setViewActive(v) {
  $("view-tabs").querySelectorAll("button").forEach((b) =>
    b.className = "rounded-md px-2.5 py-1 transition " +
      (b.dataset.view === v ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"));
}
function syncWindow() {
  const v = baseVol(); if (!v) return;
  $("win-min").value = Number(v.cal_min).toPrecision(4);
  $("win-max").value = Number(v.cal_max).toPrecision(4);
}

function wireControls() {
  $("layer-tabs").querySelectorAll("button").forEach((t) =>
    t.addEventListener("click", () => { setLayerActive(t.dataset.layer); showLayer(t.dataset.layer); }));
  $("view-tabs").querySelectorAll("button").forEach((t) =>
    t.addEventListener("click", () => { setViewActive(t.dataset.view); nv.setSliceType(nv["sliceType" + cap(t.dataset.view)]); }));
  $("cmap").addEventListener("change", () => { const v = baseVol(); if (v) { v.colormap = $("cmap").value; nv.updateGLVolume(); } });
  $("t-colorbar").addEventListener("change", (e) => { nv.opts.isColorbar = e.target.checked; nv.drawScene(); });
  $("t-crosshair").addEventListener("change", (e) => { nv.setCrosshairWidth(e.target.checked ? 0.75 : 0); });
  $("t-interp").addEventListener("change", (e) => { nv.setInterpolation(!e.target.checked); nv.drawScene(); });
  const setWin = () => { const v = baseVol(); if (!v) return; v.cal_min = parseFloat($("win-min").value); v.cal_max = parseFloat($("win-max").value); nv.updateGLVolume(); };
  $("win-min").addEventListener("change", setWin);
  $("win-max").addEventListener("change", setWin);
  $("win-auto").addEventListener("click", () => {
    const v = baseVol(); if (!v) return;
    v.cal_min = v.robust_min ?? v.global_min; v.cal_max = v.robust_max ?? v.global_max;
    nv.updateGLVolume(); syncWindow();
  });
  $("opacity").addEventListener("input", (e) => {
    for (let i = 1; i < nv.volumes.length; i++) nv.setOpacity(i, parseFloat(e.target.value));
    nv.updateGLVolume();
  });
  nv.setInterpolation(true);      // nearest-neighbour by default (Smooth unchecked)
  setViewActive("multiplanar");
}

function autoWin(vol) {  // robust percentile auto-window (the "Auto" button's behaviour)
  vol.cal_min = vol.robust_min ?? vol.global_min;
  vol.cal_max = vol.robust_max ?? vol.global_max;
}

async function showLayer(layer) {
  const cmap = $("cmap").value;
  const overlayCtl = $("overlay-ctl");
  if (layer === "error") {
    await nv.loadVolumes([{ url: baseUrl + "truth.nii.gz", colormap: cmap }]);
    autoWin(baseVol());
    await nv.addVolumeFromUrl({ url: baseUrl + "error.nii.gz", colormap: "warm", opacity: parseFloat($("opacity").value) });
    autoWin(nv.volumes[nv.volumes.length - 1]);
    overlayCtl.classList.remove("hidden"); overlayCtl.classList.add("flex");
  } else {
    await nv.loadVolumes([{ url: baseUrl + (layer === "truth" ? "truth.nii.gz" : "recon.nii.gz"), colormap: cmap }]);
    autoWin(baseVol());
    overlayCtl.classList.add("hidden"); overlayCtl.classList.remove("flex");
  }
  nv.updateGLVolume();
  syncWindow();
}

// ---- boot -------------------------------------------------------------------

async function init() {
  allRuns = await loadRuns();
  const id = new URLSearchParams(location.search).get("run");
  run = allRuns.find((r) => r.id === id) || allRuns.find((r) => r.status !== "DNF") || allRuns[0];
  if (!run) { $("sub-title").textContent = "No runs"; return; }
  navMode = run.mode === "composed" ? "pipelines" : "stages";
  $("run-filter").addEventListener("input", (e) => { filter = e.target.value; buildSidebar(); });
  document.querySelectorAll("#nav-toggle button").forEach((b) =>
    b.addEventListener("click", () => { navMode = b.dataset.mode; buildSidebar(); }));
  buildSidebar();
  loadRun();
}

init();
