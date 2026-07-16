// Submission detail + NiiVue viewer: run sidebar, in-place switching, cohesive controls,
// interactive dual-range windowing, and per-algorithm docs. Module scope; helpers via window.QSM.
import { Niivue } from "https://unpkg.com/@niivue/niivue@0.57.0/dist/index.js";

const { loadRuns, loadAlgos, loadRegistry, doiFor, METRICS, STAGE_LABEL, val, fmt } = window.QSM;

const STAGE_COLOR = {
  "field-mapping": "bg-indigo-50 text-indigo-700 ring-indigo-100 dark:bg-indigo-500/10 dark:text-indigo-300 dark:ring-indigo-500/20",
  bfr: "bg-violet-50 text-violet-700 ring-violet-100 dark:bg-violet-500/10 dark:text-violet-300 dark:ring-violet-500/20",
  dipole: "bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-100 dark:bg-fuchsia-500/10 dark:text-fuchsia-300 dark:ring-fuchsia-500/20",
};

// Stage I/O for generating "how to run" qsm-ci commands (mirrors stages.yml; magnitude is optional
// and omitted for brevity). Each stage's output filename is the next stage's input, so a composed
// pipeline chains as written.
const STAGE_IO = {
  "field-mapping": { consumes: ["phase", "mask", "params"], produces: "totalfield" },
  "bfr":           { consumes: ["totalfield", "mask", "params"], produces: "localfield" },
  "dipole":        { consumes: ["localfield", "mask", "params"], produces: "chimap" },
  "unwrap+bfr":    { consumes: ["phase", "mask", "params"], produces: "localfield" },
  "bfr+dipole":    { consumes: ["totalfield", "mask", "params"], produces: "chimap" },
  "end-to-end":    { consumes: ["phase", "mask", "params"], produces: "chimap" },
};
const ARTFILE = { phase: "phase.nii.gz", magnitude: "magnitude.nii.gz", mask: "mask.nii.gz",
  params: "params.json", totalfield: "totalfield.nii.gz", localfield: "localfield.nii.gz",
  chimap: "chimap.nii.gz" };
const escapeHtml = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

function runLine(slug, stage, truth) {
  const io = STAGE_IO[stage];
  if (!io) return `qsm-ci run ${slug}`;
  const flags = io.consumes.map((a) => `--${a} ${ARTFILE[a]}`).join(" ");
  return `qsm-ci run ${slug} ${flags} -o ${ARTFILE[io.produces]}`
    + (truth ? ` --truth ${io.produces}_groundtruth.nii.gz` : "");
}

// The qsm-ci command(s) that reproduce this run: one line for an isolated method, the
// field-mapping → bfr → dipole chain for a composed pipeline.
function renderHowToRun() {
  const el = $("how-to-run");
  if (!el) return;
  const bySlug = Object.fromEntries(algos.map((a) => [a.slug, a]));
  const stageOf = (s) => (bySlug[s] ? bySlug[s].stage : null);
  const lines = [];
  if (run.combo) {
    const { field_mapping: fm, bfr, dipole } = run.combo;
    if (fm && fm !== "gt" && stageOf(fm)) lines.push(runLine(fm, stageOf(fm), false));
    if (bfr && stageOf(bfr)) lines.push(runLine(bfr, stageOf(bfr), false));
    if (dipole && stageOf(dipole)) lines.push(runLine(dipole, stageOf(dipole), true));
  } else if (bySlug[run.slug]) {
    lines.push(runLine(run.slug, run.stage, true));
  }
  if (!lines.length) { el.style.display = "none"; return; }
  el.style.display = "";
  const full = "pip install qsm-ci\n" + lines.join("\n");
  const chained = lines.length > 1;
  el.innerHTML = `
    <div class="flex items-baseline justify-between gap-3">
      <h2 class="font-semibold text-gray-900 dark:text-gray-100">Run this yourself</h2>
      <a href="running.html" class="text-xs text-emerald-600 hover:underline">Guide to running methods →</a>
    </div>
    <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
      Reproduce it with the <a href="running.html" class="text-emerald-600 hover:underline"><code>qsm-ci</code></a> CLI —
      bring your own NIfTIs${chained ? ", chained stage by stage," : ""} or make a phantom with
      <code>qsm-forward</code>. Drop <code>--truth</code> to run without scoring.
    </p>
    <div class="relative mt-3">
      <button data-copy class="absolute right-2 top-2 rounded-md bg-gray-800/80 px-2 py-1 text-xs font-medium text-gray-100 hover:bg-gray-700">Copy</button>
      <pre class="overflow-x-auto rounded-xl bg-gray-900 p-4 text-xs leading-relaxed text-gray-100"><code>${escapeHtml(full)}</code></pre>
    </div>`;
  const btn = el.querySelector("[data-copy]");
  if (btn) btn.addEventListener("click", () => {
    navigator.clipboard.writeText(full);
    btn.textContent = "Copied"; setTimeout(() => (btn.textContent = "Copy"), 1200);
  });
}

let allRuns = [], algos = [], registry = {};
let nv = null, run, baseUrl, filter = "", navMode = "stages";
let gmin = 0, gmax = 1;  // data range for the windowing slider

const $ = (id) => document.getElementById(id);
function badge(text, cls) {
  return `<span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${cls}">${text}</span>`;
}

// ---- sidebar ----------------------------------------------------------------
const uniq = (arr) => [...new Set(arr)];
const composedRuns = () => allRuns.filter((r) => r.mode === "composed" && r.combo);
const fmapsList = () => {
  const s = uniq(composedRuns().map((r) => r.combo.field_mapping || "gt"));
  return s.includes("gt") ? ["gt", ...s.filter((x) => x !== "gt")] : s;
};
const bfrList = () => uniq(composedRuns().map((r) => r.combo.bfr));
const dipoleList = () => uniq(composedRuns().map((r) => r.combo.dipole));
const findPipeline = (f, b, d) => composedRuns().find((r) =>
  (r.combo.field_mapping || "gt") === f && r.combo.bfr === b && r.combo.dipole === d);
const fmapName = (m) => (m === "gt" ? "ground truth" : m);

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
  return `<button data-id="${r ? r.id : ""}"
    class="run-item w-full text-left rounded-lg px-2.5 py-1.5 text-sm flex items-center justify-between gap-2 transition
      ${active ? "bg-indigo-50 text-indigo-700 font-medium dark:bg-indigo-500/15 dark:text-indigo-300" : "text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800"} ${!r ? "opacity-40 cursor-default" : ""}">
    <span class="truncate">%NAME%</span>
    <span class="shrink-0 tabular-nums text-xs ${dis ? "text-gray-300 dark:text-gray-600" : active ? "text-indigo-500" : "text-gray-400"}">${label}</span>
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
  if (!composedRuns().length)
    return `<p class="p-3 text-sm text-gray-400">No pipeline combinations available yet — the composed matrix is computed by the nightly job.</p>`;
  const cur = currentCombo();
  const f = filter.toLowerCase();
  const axis = (title, methods, kind) => {
    const rows = methods.filter((m) => { const nm = kind === "fmap" ? fmapName(m) : m; return !f || nm.toLowerCase().includes(f); }).map((m) => {
      const rn = kind === "fmap" ? findPipeline(m, cur.bfr, cur.dipole)
        : kind === "bfr" ? findPipeline(cur.fmap, m, cur.dipole) : findPipeline(cur.fmap, cur.bfr, m);
      return runItem(rn, run?.id).replace("%NAME%", kind === "fmap" ? fmapName(m) : m);
    }).join("");
    return `<div class="mb-3"><div class="px-2.5 pt-1 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">${title}</div>${rows}</div>`;
  };
  return axis("Field mapping", fmapsList(), "fmap") + axis("Background removal", bfrList(), "bfr") + axis("Dipole inversion", dipoleList(), "dipole");
}
function buildSidebar() {
  document.querySelectorAll("#nav-toggle button").forEach((b) =>
    b.className = "flex-1 rounded-md px-2 py-1 transition " +
      (b.dataset.mode === navMode ? "bg-white shadow-sm text-gray-900 dark:bg-gray-700 dark:text-gray-100" : "text-gray-500 hover:text-gray-700 dark:text-gray-400"));
  $("run-list").innerHTML = navMode === "stages" ? stagesHTML() : pipelinesHTML();
  $("run-list").querySelectorAll(".run-item").forEach((b) => b.addEventListener("click", () => { if (b.dataset.id) selectRun(b.dataset.id); }));
}
function selectRun(id) {
  run = allRuns.find((r) => r.id === id);
  history.replaceState(null, "", "?run=" + encodeURIComponent(id));
  buildSidebar();
  loadRun();
}

// ---- method docs ------------------------------------------------------------
function methodCard(a) {
  if (!a) return "";
  const links = [];
  const zdoi = doiFor(registry, a.slug);
  if (zdoi) links.push(`<a href="${zdoi.url}" class="text-emerald-600 hover:underline" title="Cite this QSM-CI submission (Zenodo v${zdoi.version})">submission doi (v${zdoi.version})</a>`);
  if (a.doi) links.push(`<a href="https://doi.org/${a.doi}" class="text-indigo-600 hover:underline">paper doi</a>`);
  if (a.code_url) links.push(`<a href="${a.code_url}" class="text-indigo-600 hover:underline">source</a>`);
  const params = (a.parameters || []).map((p) =>
    `<tr class="border-t border-gray-100 dark:border-gray-800"><td class="py-1 pr-3 font-mono text-gray-700 dark:text-gray-300">${p.name}</td><td class="py-1 pr-3 tabular-nums text-gray-500 dark:text-gray-400">${p.default}</td><td class="py-1 text-gray-400 dark:text-gray-500">${p.description || ""}</td></tr>`).join("");
  return `<div>
    <div class="flex items-baseline gap-2">
      <span class="font-medium text-gray-900 dark:text-gray-100">${a.name}</span>
      <span class="text-xs text-gray-400">${a.stage ? (STAGE_LABEL[a.stage] || a.stage) : ""}</span>
    </div>
    <p class="mt-0.5 text-sm text-gray-600 dark:text-gray-400">${a.description || ""}</p>
    ${params ? `<table class="mt-2 w-full text-xs"><tbody>${params}</tbody></table>` : ""}
    ${(a.citation || links.length) ? `<p class="mt-1.5 text-xs text-gray-400 dark:text-gray-500">${a.citation || ""} ${links.length ? "· " + links.join(" · ") : ""}</p>` : ""}
  </div>`;
}
function renderMethodInfo() {
  const el = $("method-info");
  const bySlug = Object.fromEntries(algos.map((a) => [a.slug, a]));
  const cards = [];
  if (run.combo) {
    for (const s of [run.combo.field_mapping, run.combo.bfr, run.combo.dipole])
      if (s && s !== "gt" && bySlug[s]) cards.push(methodCard(bySlug[s]));
  } else if (bySlug[run.slug]) {
    cards.push(methodCard(bySlug[run.slug]));
  }
  el.innerHTML = cards.join('<div class="border-t border-gray-100 dark:border-gray-800 pt-2"></div>');
  el.style.display = cards.length ? "" : "none";
}

// ---- detail + viewer --------------------------------------------------------
async function loadRun() {
  $("sub-title").textContent = run.name;
  const stageCls = STAGE_COLOR[run.stage] || "bg-gray-100 text-gray-600 ring-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:ring-gray-700";
  $("sub-badges").innerHTML =
    badge(STAGE_LABEL[run.stage] || run.stage, stageCls) +
    badge(run.mode === "composed" ? "Composed pipeline" : "Isolated", "bg-gray-100 text-gray-600 ring-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:ring-gray-700") +
    (run.status === "DNF" ? badge("DNF", "bg-red-50 text-red-600 ring-red-100 dark:bg-red-500/10 dark:text-red-400 dark:ring-red-500/20") : "");
  const bits = [];
  if (run.artifact) bits.push(`scored artifact <code class="text-gray-700 dark:text-gray-300">${run.artifact}</code>`);
  if (run.runtime_s != null) bits.push(`runtime ${run.runtime_s.toFixed(1)}s`);
  if (run.image) bits.push(`image <code class="text-gray-700 dark:text-gray-300">${run.image}</code>`);
  $("sub-meta").innerHTML = bits.join(" · ");
  renderMethodInfo();
  renderHowToRun();
  renderMetrics();

  const note = $("viewer-note"), canvas = $("gl1"), controls = $("viewer-controls"), layerRow = $("layer-row");
  const hide = (el, h) => { el.style.display = h ? "none" : ""; };
  if (run.status === "DNF") {
    canvas.style.visibility = "hidden"; hide(controls, true); hide(layerRow, true);
    note.textContent = "This run did not produce a valid output (DNF).";
    note.classList.remove("hidden"); note.classList.add("flex");
    return;
  }
  canvas.style.visibility = "visible"; hide(controls, false); hide(layerRow, false);
  note.classList.add("hidden"); note.classList.remove("flex");

  baseUrl = `results/${run.id}/`;
  if (!nv) {
    nv = new Niivue({
      isColorbar: false, textHeight: 0.03, show3Dcrosshair: false, crosshairWidth: 0.75, backColor: [0, 0, 0, 1],
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
  $("metrics-sub").textContent = run.mode === "composed" ? "Final χ map vs. ground truth" : `${run.artifact || "output"} vs. ground truth`;
  const order = Object.keys(METRICS).filter((k) => m[k] != null);
  $("metrics-body").innerHTML = order.map((k) => {
    const meta = METRICS[k], arrow = meta.better === "higher" ? "↑" : "↓", hero = k === "xsim" || k === "nrmse";
    return `<tr>
      <td class="py-2.5 text-gray-500 dark:text-gray-400">${meta.label} <span class="text-gray-300 dark:text-gray-600" title="${meta.better} is better">${arrow}</span></td>
      <td class="py-2.5 text-right tabular-nums ${hero ? "font-bold text-gray-900 dark:text-gray-100" : "font-medium text-gray-700 dark:text-gray-300"}">${fmt(m[k], k)}</td>
    </tr>`;
  }).join("") || `<tr><td class="py-3 text-gray-400">No metrics for this run.</td></tr>`;
}

// ---- controls ---------------------------------------------------------------
const cap = (s) => s[0].toUpperCase() + s.slice(1);
const baseVol = () => nv.volumes[0];
function setLayerActive(layer) {
  $("layer-tabs").querySelectorAll("button").forEach((t) =>
    t.className = "rounded-md px-3 py-1 transition " +
      (t.dataset.layer === layer ? "bg-white shadow-sm text-gray-900 dark:bg-gray-700 dark:text-gray-100" : "text-gray-500 hover:text-gray-700 dark:text-gray-400"));
}
function setViewActive(v) {
  $("view-tabs").querySelectorAll("button").forEach((b) =>
    b.className = "rounded-md px-2.5 py-1 transition " +
      (b.dataset.view === v ? "bg-indigo-600 text-white dark:bg-indigo-500" : "text-gray-500 hover:text-gray-700 dark:text-gray-400"));
}
function autoWin(vol) { vol.cal_min = vol.robust_min ?? vol.global_min; vol.cal_max = vol.robust_max ?? vol.global_max; }
function defaultWindow(vol) {
  if (run.kind === "chi") { vol.cal_min = -0.1; vol.cal_max = 0.1; }  // χ maps: fixed ±0.1 ppm
  else autoWin(vol);                                                  // fields / everything else: auto
}
const fmtWin = (v) => (Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 1 ? v.toFixed(2) : v.toPrecision(2));

function setupWindow() {
  const v = baseVol(); if (!v) return;
  gmin = v.global_min; gmax = v.global_max;
  const step = (gmax - gmin) / 1000 || 1e-6;
  for (const el of [$("win-lo"), $("win-hi")]) { el.min = gmin; el.max = gmax; el.step = step; }
  $("win-lo").value = v.cal_min; $("win-hi").value = v.cal_max;
  updateWindowUI();
}
function updateWindowUI() {
  let lo = parseFloat($("win-lo").value), hi = parseFloat($("win-hi").value);
  if (lo > hi) { [lo, hi] = [hi, lo]; }
  const v = baseVol(); if (v) { v.cal_min = lo; v.cal_max = hi; nv.updateGLVolume(); }
  const pct = (x) => (gmax === gmin ? 0 : ((x - gmin) / (gmax - gmin)) * 100);
  $("win-fill").style.left = pct(lo) + "%";
  $("win-fill").style.width = (pct(hi) - pct(lo)) + "%";
  $("win-lo-bubble").style.left = pct(lo) + "%"; $("win-lo-bubble").textContent = fmtWin(lo);
  $("win-hi-bubble").style.left = pct(hi) + "%"; $("win-hi-bubble").textContent = fmtWin(hi);
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
  $("win-lo").addEventListener("input", updateWindowUI);
  $("win-hi").addEventListener("input", updateWindowUI);
  $("win-auto").addEventListener("click", () => { const v = baseVol(); if (!v) return; autoWin(v); $("win-lo").value = v.cal_min; $("win-hi").value = v.cal_max; updateWindowUI(); });
  $("opacity").addEventListener("input", (e) => { for (let i = 1; i < nv.volumes.length; i++) nv.setOpacity(i, parseFloat(e.target.value)); nv.updateGLVolume(); });
  nv.setInterpolation(true);
  setViewActive("multiplanar");
}

// Volumes are served from the Hugging Face Hub (run.volumes[kind]); fall back to local results/<id>/ for dev.
const volUrl = (kind) => (run && run.volumes && run.volumes[kind]) || (baseUrl + kind + ".nii.gz");

async function showLayer(layer) {
  const cmap = $("cmap").value, overlayCtl = $("overlay-ctl");
  if (layer === "error") {
    await nv.loadVolumes([{ url: volUrl("truth"), colormap: cmap }]);
    defaultWindow(baseVol());
    await nv.addVolumeFromUrl({ url: volUrl("error"), colormap: "warm", opacity: parseFloat($("opacity").value) });
    autoWin(nv.volumes[nv.volumes.length - 1]);
    overlayCtl.classList.remove("hidden"); overlayCtl.classList.add("flex");
  } else {
    await nv.loadVolumes([{ url: volUrl(layer === "truth" ? "truth" : "recon"), colormap: cmap }]);
    defaultWindow(baseVol());
    overlayCtl.classList.add("hidden"); overlayCtl.classList.remove("flex");
  }
  nv.updateGLVolume();
  setupWindow();
}

// ---- boot -------------------------------------------------------------------
async function init() {
  [allRuns, algos, registry] = await Promise.all([loadRuns(), loadAlgos(), loadRegistry()]);
  const id = new URLSearchParams(location.search).get("run");
  run = allRuns.find((r) => r.id === id) || allRuns.find((r) => r.status !== "DNF") || allRuns[0];
  if (!run) { $("sub-title").textContent = "No runs"; return; }
  navMode = run.mode === "composed" ? "pipelines" : "stages";
  $("run-filter").addEventListener("input", (e) => { filter = e.target.value; buildSidebar(); });
  document.querySelectorAll("#nav-toggle button").forEach((b) => b.addEventListener("click", () => { navMode = b.dataset.mode; buildSidebar(); }));
  buildSidebar();
  loadRun();
}
init();
