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
const fmapsList = () => uniq(composedRuns().map((r) => r.combo.field_mapping || "gt"));
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

function pipelinesHTML() {
  const cur = currentCombo();
  const f = filter.toLowerCase();
  const fmaps = fmapsList();
  const fmSel = fmaps.length > 1
    ? `<div class="px-1 pb-3"><select id="pl-fmap" class="w-full rounded-lg border-gray-300 text-sm py-1.5">
        ${fmaps.map((x) => `<option value="${x}" ${x === cur.fmap ? "selected" : ""}>Field: ${x === "gt" ? "ground truth" : x}</option>`).join("")}</select></div>`
    : "";
  const axis = (title, methods, kind) => {
    const rows = methods.filter((m) => !f || m.toLowerCase().includes(f)).map((m) => {
      const rn = kind === "bfr" ? findPipeline(cur.fmap, m, cur.dipole) : findPipeline(cur.fmap, cur.bfr, m);
      return runItem(rn, run?.id).replace("%NAME%", m);
    }).join("");
    return `<div class="mb-3"><div class="px-2.5 pt-1 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">${title}</div>${rows}</div>`;
  };
  return fmSel + axis("Background removal", bfrList(), "bfr") + axis("Dipole inversion", dipoleList(), "dipole");
}

function buildSidebar() {
  document.querySelectorAll("#nav-toggle button").forEach((b) =>
    b.className = "flex-1 rounded-md px-2 py-1 transition " +
      (b.dataset.mode === navMode ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"));
  $("run-list").innerHTML = navMode === "stages" ? stagesHTML() : pipelinesHTML();
  $("run-list").querySelectorAll(".run-item").forEach((b) =>
    b.addEventListener("click", () => { if (b.dataset.id) selectRun(b.dataset.id); }));
  const sel = $("pl-fmap");
  if (sel) sel.addEventListener("change", () => {
    const cur = currentCombo();
    const rn = findPipeline(sel.value, cur.bfr, cur.dipole);
    if (rn) selectRun(rn.id);
  });
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
  navMode = run.mode === "composed" ? "pipelines" : "stages";
  $("run-filter").addEventListener("input", (e) => { filter = e.target.value; buildSidebar(); });
  document.querySelectorAll("#nav-toggle button").forEach((b) =>
    b.addEventListener("click", () => { navMode = b.dataset.mode; buildSidebar(); }));
  buildSidebar();
  loadRun();
}

init();
