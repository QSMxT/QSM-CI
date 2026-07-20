// Submission detail + NiiVue viewer: run sidebar, in-place switching, cohesive controls,
// histogram-backed dual-range windowing with typed bounds, and per-algorithm docs.
// Module scope; helpers via window.QSM.
import { Niivue } from "https://unpkg.com/@niivue/niivue@0.57.0/dist/index.js";

const { loadRuns, loadAlgos, loadRegistry, doiFor, METRICS, STAGE_LABEL, val, fmt, robustRange, heatScale } = window.QSM;

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
  // One flag per line, backslash-continued, so long commands don't overflow the code block.
  const parts = [`qsm-ci run ${slug}`, ...io.consumes.map((a) => `--${a} ${ARTFILE[a]}`),
    `-o ${ARTFILE[io.produces]}`];
  if (truth) parts.push(`--truth ${io.produces}_groundtruth.nii.gz`);
  return parts.join(" \\\n  ");
}

// The qsm-ci command(s) that reproduce this run: one line for an isolated method, the
// field-mapping → bfr → dipole chain for a composed pipeline.
// QSM-CI reproduces the scored artifact; QSMxT runs the same method(s) end-to-end from BIDS. Which
// slugs QSMxT can run is read from each algorithm's self-described `engine` (contains "QSM.rs") — no
// per-method hardcoding — and the qsmxt flag follows from the stage.
const QSMXT_FLAG = {
  bfr: "--bf-algorithm", "unwrap+bfr": "--bf-algorithm",
  dipole: "--qsm-algorithm", "bfr+dipole": "--qsm-algorithm", "end-to-end": "--qsm-algorithm",
};
function renderHowToRun() {
  const el = $("how-to-run");
  if (!el) return;
  const bySlug = Object.fromEntries(algos.map((a) => [a.slug, a]));
  const stageOf = (s) => (bySlug[s] ? bySlug[s].stage : null);
  const isQsmRs = (slug) => { const a = bySlug[slug]; return !!(a && a.engine && a.engine.includes("QSM.rs")); };

  // ---- QSM-CI command (reproduces the scored artifact) ----
  const lines = [];
  if (run.combo) {
    const { field_mapping: fm, bfr, dipole } = run.combo;
    if (fm && fm !== "gt" && stageOf(fm)) lines.push(runLine(fm, stageOf(fm), false));
    if (bfr && stageOf(bfr)) lines.push(runLine(bfr, stageOf(bfr), false));
    if (dipole && stageOf(dipole)) lines.push(runLine(dipole, stageOf(dipole), true));
  } else if (bySlug[run.slug]) {
    lines.push(runLine(run.slug, run.stage, true));
  }
  if (!lines.length) { el.classList.add("hidden"); return; }
  const ciCmd = "pip install qsm-ci\n" + lines.join("\n");
  const chained = lines.length > 1;

  // ---- QSMxT command (only when every method step is QSM.rs-backed) ----
  const xtCmd = (() => {
    const parts = ["qsmxt run /path/to/bids /path/to/output"];
    if (run.combo) {
      const { field_mapping: fm, bfr, dipole } = run.combo;
      if (!isQsmRs(bfr) || !isQsmRs(dipole)) return null;
      if (fm && fm !== "gt") { if (!isQsmRs(fm)) return null; parts.push(`--unwrapping-algorithm ${fm.replace(/-fieldmap$/, "")}`); }
      parts.push(`--bf-algorithm ${bfr}`, `--qsm-algorithm ${dipole}`);
    } else {
      if (!isQsmRs(run.slug) || !QSMXT_FLAG[run.stage]) return null;
      parts.push(`${QSMXT_FLAG[run.stage]} ${run.slug}`);
    }
    return parts.join(" \\\n  ");
  })();

  el.classList.remove("hidden");  // the div ships with Tailwind `hidden`; clear the class, not just inline style

  const codePane = (cmd, key, hidden) =>
    `<div data-pane="${key}" class="relative mt-3 ${hidden ? "hidden" : ""}">
      <button data-copy="${key}" class="absolute right-2 top-2 rounded-md bg-gray-800/80 px-2 py-1 text-xs font-medium text-gray-100 hover:bg-gray-700">Copy</button>
      <pre class="overflow-x-auto rounded-xl bg-gray-900 p-4 text-xs leading-relaxed text-gray-100"><code>${escapeHtml(cmd)}</code></pre>
    </div>`;
  const tabBtn = (key, label, active) =>
    `<button data-tab="${key}" class="rounded-md px-3 py-1 transition ${active ? "bg-white shadow-sm text-gray-900 dark:bg-gray-700 dark:text-gray-100" : "text-gray-500 hover:text-gray-700 dark:text-gray-400"}">${label}</button>`;

  const ciDesc = `Reproduce the scored artifact with the <a href="running.html" class="text-emerald-600 hover:underline"><code>qsm-ci</code></a> CLI —
      bring your own NIfTIs${chained ? ", chained stage by stage," : ""} or make a phantom with <code>qsm-forward</code>. Drop <code>--truth</code> to run without scoring.`;
  const xtDesc = `Run this ${run.combo ? "pipeline" : "method"} end-to-end on your own BIDS data with
      <a href="https://qsmxt.github.io" class="text-emerald-600 hover:underline">QSMxT</a> — unwrapping, background removal and dipole
      inversion in one command, on the same <a href="https://github.com/astewartau/QSM.rs" class="text-emerald-600 hover:underline">QSM.rs</a> engine QSM-CI uses.`;

  el.innerHTML = `
    <div class="flex items-baseline justify-between gap-3">
      <h2 class="font-semibold text-gray-900 dark:text-gray-100">Run this yourself</h2>
      <a href="running.html" class="text-xs text-emerald-600 hover:underline">Guide to running algorithms →</a>
    </div>
    ${xtCmd ? `<div class="mt-2 inline-flex rounded-lg bg-gray-100 p-1 text-xs font-medium dark:bg-gray-800" data-howto-tabs>${tabBtn("ci", "QSM-CI", true)}${tabBtn("xt", "QSMxT", false)}</div>` : ""}
    <p data-desc="ci" class="mt-2 text-sm text-gray-600 dark:text-gray-400">${ciDesc}</p>
    ${xtCmd ? `<p data-desc="xt" class="mt-2 hidden text-sm text-gray-600 dark:text-gray-400">${xtDesc}</p>` : ""}
    ${codePane(ciCmd, "ci", false)}
    ${xtCmd ? codePane(xtCmd, "xt", true) : ""}`;

  const cmds = { ci: ciCmd, xt: xtCmd };
  el.querySelectorAll("[data-copy]").forEach((btn) => btn.addEventListener("click", () => {
    navigator.clipboard.writeText(cmds[btn.dataset.copy]);
    btn.textContent = "Copied"; setTimeout(() => (btn.textContent = "Copy"), 1200);
  }));
  const tabs = el.querySelector("[data-howto-tabs]");
  if (tabs) tabs.querySelectorAll("[data-tab]").forEach((b) => b.addEventListener("click", () => {
    const key = b.dataset.tab;
    tabs.querySelectorAll("[data-tab]").forEach((t) =>
      t.className = "rounded-md px-3 py-1 transition " + (t.dataset.tab === key ? "bg-white shadow-sm text-gray-900 dark:bg-gray-700 dark:text-gray-100" : "text-gray-500 hover:text-gray-700 dark:text-gray-400"));
    for (const k of ["ci", "xt"]) {
      el.querySelector(`[data-pane="${k}"]`)?.classList.toggle("hidden", k !== key);
      el.querySelector(`[data-desc="${k}"]`)?.classList.toggle("hidden", k !== key);
    }
  }));
}

let allRuns = [], algos = [], registry = {};
let nv = null, run, baseUrl, filter = "", navMode = "stages";
let curBase = "recon";       // base map shown underneath: recon | truth
let showError = false;       // whether the error map is overlaid on top of the base
let loadedBase = null, loadedError = false;  // what's actually in nv.volumes right now
let baseCtl = null, errorCtl = null;         // the two windowing controls (base + error overlay)

const $ = (id) => document.getElementById(id);
function badge(text, cls) {
  return `<span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${cls}">${text}</span>`;
}

// ---- sidebar ----------------------------------------------------------------
const uniq = (arr) => [...new Set(arr)];
const composedRuns = () => allRuns.filter((r) => r.mode === "composed" && r.combo);
// Combined single-step methods (bfr+dipole / end-to-end, e.g. NeXtQSM/TGV/QSMART/MEDI/iQSM) go
// straight to a chi map in one step, so they have no fmap×bfr×dipole combo and are missed by the
// matrix axes. Surface them as their own Pipelines group — one run per slug, preferring the composed
// representation. (unwrap+bfr methods produce localfield, not chi, so they sit on the matrix's
// background-removal axis instead and are excluded here.)
const combinedRuns = () => {
  const bySlug = {};
  for (const r of allRuns) {
    if (r.combo) continue;  // matrix combos carry stage bfr+dipole too — they belong on the axes
    if (r.stage !== "bfr+dipole" && r.stage !== "end-to-end") continue;
    if (!bySlug[r.slug] || r.mode === "composed") bySlug[r.slug] = r;
  }
  return Object.values(bySlug);
};
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
  // Pipeline order: field mapping → background removal → dipole inversion, then the combined
  // single-method spans (bfr+dipole like TGV/QSMART/MEDI, unwrap+bfr like HARPERELLA, end-to-end).
  return ["field-mapping", "bfr", "dipole", "bfr+dipole", "unwrap+bfr", "end-to-end"].map((s) => {
    const rs = allRuns.filter((r) => r.mode === "isolated" && r.stage === s && (!f || r.name.toLowerCase().includes(f)));
    if (!rs.length) return "";
    const rows = rs.map((r) => runItem(r, run?.id).replace("%NAME%", r.name)).join("");
    return `<div class="mb-3"><div class="px-2.5 pt-1 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">${STAGE_LABEL[s] || s}</div>${rows}</div>`;
  }).join("") || `<p class="p-3 text-sm text-gray-400">No matches.</p>`;
}
function pipelinesHTML() {
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
  const matrix = composedRuns().length
    ? axis("Field mapping", fmapsList(), "fmap") + axis("Background removal", bfrList(), "bfr") + axis("Dipole inversion", dipoleList(), "dipole")
    : "";
  // Single-step χ producers, grouped by their self-described stage (not hardcoded per method) — the
  // same split as the Stages view and the leaderboard: bfr+dipole and end-to-end are distinct spans.
  const combined = combinedRuns().filter((r) => !f || r.name.toLowerCase().includes(f));
  const combinedGroup = (stage) => {
    const rs = combined.filter((r) => r.stage === stage);
    return rs.length
      ? `<div class="mb-3"><div class="px-2.5 pt-1 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">${STAGE_LABEL[stage] || stage}</div>${rs.map((r) => runItem(r, run?.id).replace("%NAME%", r.name)).join("")}</div>`
      : "";
  };
  const combinedSection = combinedGroup("bfr+dipole") + combinedGroup("end-to-end");
  return (matrix + combinedSection) ||
    `<p class="p-3 text-sm text-gray-400">No pipeline combinations available yet — the composed matrix is computed by the nightly job.</p>`;
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
  if (zdoi) links.push(`<a href="${zdoi.url}" class="text-emerald-600 hover:underline" title="Cite this QSM-CI submission (Zenodo v${zdoi.version})">submission doi</a>`);
  if (a.doi) links.push(`<a href="https://doi.org/${a.doi}" class="text-indigo-600 hover:underline">paper doi</a>`);
  if (a.code_url) links.push(`<a href="${a.code_url}" class="text-indigo-600 hover:underline">source code</a>`);
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
  // New run → nothing loaded yet; the base map (recon/truth) selection carries over between runs.
  loadedBase = null; loadedError = false;
  const hasError = !run.volumes || !!run.volumes.error;  // HF-backed runs advertise which volumes exist
  if (!hasError) showError = false;
  $("t-error").disabled = !hasError;
  $("t-error").checked = showError;
  setLayerActive(curBase);
  try { await refreshView(); } catch (e) {
    canvas.style.visibility = "hidden";
    note.textContent = "Interactive volumes aren't available for this run.";
    note.classList.remove("hidden"); note.classList.add("flex");
  }
}

// Rank this run's value for metric `k` among comparable runs (same job: composed pipelines together,
// or isolated runs sharing this run's stage). Returns { rank, n, t } where t is 0..1 goodness for
// colour, or null when there's nothing to compare against.
function metricRank(k) {
  const meta = METRICS[k], v = run.metrics?.[k];
  if (v == null) return null;
  const sameGroup = (r) => (run.combo ? r.mode === "composed" : r.mode === "isolated" && r.stage === run.stage);
  const peers = allRuns.filter((r) => r.status !== "DNF" && sameGroup(r) && val(r, k) != null);
  if (peers.length < 2) return null;
  const higher = meta.better !== "lower";
  const rank = 1 + peers.filter((r) => (higher ? val(r, k) > v : val(r, k) < v)).length;
  const [lo, hi] = robustRange(peers.map((r) => val(r, k)));
  let t = hi === lo ? 0.5 : (v - lo) / (hi - lo);
  if (!higher) t = 1 - t;
  return { rank, n: peers.length, t };
}

function renderMetrics() {
  const m = run.metrics || {};
  $("metrics-sub").textContent = run.mode === "composed" ? "Final χ map vs. ground truth" : `${run.artifact || "output"} vs. ground truth`;
  const order = Object.keys(METRICS).filter((k) => m[k] != null);
  const groupLabel = run.combo ? "composed pipelines" : `isolated ${STAGE_LABEL[run.stage] || run.stage} methods`;
  $("metrics-body").innerHTML = order.map((k) => {
    const meta = METRICS[k], arrow = meta.better === "higher" ? "↑" : "↓", hero = k === "xsim" || k === "nrmse";
    const rk = metricRank(k);
    const rankCell = rk
      ? `<span class="inline-block rounded-md px-1.5 py-0.5 text-xs font-semibold text-white shadow-sm" style="background:${heatScale(rk.t)}" data-tip="Rank ${rk.rank} of ${rk.n} ${groupLabel} for ${meta.label}">#${rk.rank}<span class="opacity-70"> / ${rk.n}</span></span>`
      : `<span class="text-gray-300 dark:text-gray-600">—</span>`;
    return `<tr>
      <td class="py-2.5 text-gray-500 dark:text-gray-400"><span class="has-tip" data-tip="${(meta.desc || "").replace(/"/g, "&quot;")}">${meta.label}</span> <span class="text-gray-300 dark:text-gray-600" title="${meta.better} is better">${arrow}</span></td>
      <td class="py-2.5 text-right tabular-nums ${hero ? "font-bold text-gray-900 dark:text-gray-100" : "font-medium text-gray-700 dark:text-gray-300"}">${fmt(m[k], k)}</td>
      <td class="py-2.5 pl-3 text-right">${rankCell}</td>
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
const fmtNum = (v) => String(+Number(v).toPrecision(4));

// Colormaps for the error overlay. Every option windows on |error| with a transparency floor (so the
// masked, near-zero background stays clear); "diverging" colours the two signs differently (NiiVue
// colormapNegative) for a signed red↔blue view, the rest reuse one map for both signs (magnitude only).
const ERROR_CMAPS = {
  diverging: { colormap: "warm", colormapNegative: "winter" },  // signed: red = recon>truth, blue = recon<truth
  warm:    { colormap: "warm",    colormapNegative: "warm" },
  hot:     { colormap: "hot",     colormapNegative: "hot" },
  viridis: { colormap: "viridis", colormapNegative: "viridis" },
  plasma:  { colormap: "plasma",  colormapNegative: "plasma" },
  cool:    { colormap: "cool",    colormapNegative: "cool" },
  gray:    { colormap: "gray",    colormapNegative: "gray" },
};

function setLoading(on) {
  const el = $("viewer-loading");
  el.classList.toggle("hidden", !on);
  el.classList.toggle("flex", on);
}

// A self-contained windowing control: label, typed lo/hi bounds, Auto, a dual-range slider and an
// intensity histogram drawn behind it. `getVol` returns the NiiVue volume it drives, so the same
// widget serves both the base map and the error overlay. Instances live in `winControls` so a theme
// toggle or resize can repaint every histogram at once. cal_min/cal_max are the source of truth;
// typed bounds may fall outside [global_min, global_max] (the slider thumb clamps, the volume doesn't).
const winControls = [];
function makeWindowControl(getVol, cmapCfg) {
  const el = document.createElement("div");
  el.innerHTML = `
    <div class="flex items-center gap-2">
      <div class="dualrange flex-1" title="Scroll to zoom the range · double-click to reset">
        <canvas class="hist"></canvas>
        <div class="track"></div><div class="fill"></div>
        <input class="rng-lo" type="range" /><input class="rng-hi" type="range" />
        <span class="win-bubble bub-lo" contenteditable="true" inputmode="decimal" spellcheck="false" title="Click to edit this bound"></span>
        <span class="win-bubble bub-hi" contenteditable="true" inputmode="decimal" spellcheck="false" title="Click to edit this bound"></span>
      </div>
      <div class="flex w-28 shrink-0 flex-col gap-1.5">
        <select class="cmap-sel hidden w-full !py-1 !pl-2 !pr-6 text-[11px] leading-tight" title="Colormap"></select>
        <button class="btn-auto w-full rounded-lg bg-white px-2.5 py-1 text-xs font-medium text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-200 dark:ring-gray-700" title="Reset to an automatic window">Auto</button>
      </div>
    </div>
    <div class="zoom-hint mt-0.5 text-[10px] text-gray-400 dark:text-gray-500"></div>`;
  const q = (s) => el.querySelector(s);
  const rngLo = q(".rng-lo"), rngHi = q(".rng-hi"),
    fill = q(".fill"), bubLo = q(".bub-lo"), bubHi = q(".bub-hi"), canvas = q(".hist"),
    dr = q(".dualrange"), hintEl = q(".zoom-hint"), cmapSel = q(".cmap-sel");
  // Optional compact colormap dropdown sits above the Auto button. Fixed-width so a long selection
  // (e.g. "Diverging (red ↔ blue)") truncates rather than widening the control; the native option list
  // still shows each label in full.
  if (cmapCfg) {
    cmapSel.classList.remove("hidden");
    cmapSel.innerHTML = cmapCfg.options.map(([v, l]) => `<option value="${v}">${l}</option>`).join("");
    cmapSel.value = cmapCfg.value;
    cmapSel.addEventListener("change", () => cmapCfg.onChange(cmapSel.value));
  }
  // magnitude=true windows on |value| over [0, maxAbs] — used for the signed error map under a diverging
  // colormap, where cal_min/cal_max act as a magnitude transparency floor + saturation (mirrored to negatives).
  // [dmin,dmax] is the full data range; [vmin,vmax] is the zoomed *view* the slider+histogram span, so
  // scrolling to a narrow view makes each pixel of drag fine. cal_min/cal_max stay the source of truth.
  let dmin = 0, dmax = 1, vmin = 0, vmax = 1, winLo = 0, winHi = 1, hist = null, magnitude = false;
  const clampV = (x) => Math.min(vmax, Math.max(vmin, x));  // into the zoom view; thumbs pin, cal_* stay exact
  const pct = (x) => (vmax === vmin ? 0 : ((clampV(x) - vmin) / (vmax - vmin)) * 100);

  // Read the volume's current window + data range, reset the zoom to the full range, and sync the UI.
  function setup() {
    const v = getVol(); if (!v) return;
    if (magnitude) { dmin = 0; dmax = Math.max(Math.abs(v.global_min), Math.abs(v.global_max)) || 1; }
    else { dmin = v.global_min; dmax = v.global_max; }
    vmin = dmin; vmax = dmax;
    winLo = v.cal_min; winHi = v.cal_max;
    applyView();
  }
  // Re-point the slider + histogram at the current zoom view [vmin,vmax] and reposition the window.
  function applyView() {
    const step = (vmax - vmin) / 1000 || 1e-6;
    for (const r of [rngLo, rngHi]) { r.min = vmin; r.max = vmax; r.step = step; }
    const zoomed = vmax - vmin < (dmax - dmin) * 0.999;
    hintEl.textContent = zoomed
      ? `zoomed to ${fmtWin(vmin)} – ${fmtWin(vmax)} · double-click to reset`
      : "scroll over the bar to zoom in for finer control";
    buildHistogram(getVol());
    apply(winLo, winHi);
  }
  // Zoom the view by `factor` about the value under `frac` (0..1 across the bar), clamped to the data.
  function zoom(factor, frac) {
    const full = dmax - dmin || 1;
    const span = Math.min(full, Math.max(full / 5000, (vmax - vmin) * factor));
    const center = vmin + frac * (vmax - vmin);
    let nmin = center - frac * span, nmax = nmin + span;
    if (nmin < dmin) { nmin = dmin; nmax = dmin + span; }
    if (nmax > dmax) { nmax = dmax; nmin = dmax - span; }
    vmin = nmin; vmax = nmax;
    applyView();
  }
  function apply(lo, hi) {
    if (!isFinite(lo)) lo = dmin;
    if (!isFinite(hi)) hi = dmax;
    if (lo > hi) [lo, hi] = [hi, lo];
    if (magnitude) { lo = Math.max(0, lo); hi = Math.max(0, hi); }  // magnitudes only
    winLo = lo; winHi = hi;
    const v = getVol(); if (v) { v.cal_min = lo; v.cal_max = hi; nv.updateGLVolume(); }
    rngLo.value = clampV(lo); rngHi.value = clampV(hi);
    fill.style.left = pct(lo) + "%"; fill.style.width = (pct(hi) - pct(lo)) + "%";
    if (document.activeElement !== bubLo) bubLo.textContent = fmtWin(lo);  // don't clobber a bubble mid-edit
    if (document.activeElement !== bubHi) bubHi.textContent = fmtWin(hi);
    positionBubbles();
    draw();
  }
  // Place the two value bubbles at their thumbs, but when they'd overlap nudge them apart symmetrically
  // (clamped to the bar edges) so both stay readable when the bounds are close together.
  function positionBubbles() {
    const bw = dr.clientWidth || 1;
    let cLo = (pct(winLo) / 100) * bw, cHi = (pct(winHi) / 100) * bw;
    const wLo = bubLo.offsetWidth, wHi = bubHi.offsetWidth, minSep = wLo / 2 + wHi / 2 + 4;
    if (cHi - cLo < minSep) {
      const mid = (cLo + cHi) / 2;
      cLo = mid - minSep / 2; cHi = mid + minSep / 2;
      if (cLo < wLo / 2) { cLo = wLo / 2; cHi = cLo + minSep; }
      if (cHi > bw - wHi / 2) { cHi = bw - wHi / 2; cLo = cHi - minSep; }
    }
    bubLo.style.left = cLo + "px"; bubHi.style.left = cHi + "px";
  }
  // Intensity histogram over the current zoom view. Exact-zero voxels are skipped (the masked background
  // dominates otherwise) and counts are log-scaled so the tissue distribution stays visible next to the mode.
  function buildHistogram(v) {
    hist = null;
    const img = v && v.img;
    if (img && img.length && vmax > vmin) {
      const slope = v.hdr?.scl_slope || 1, inter = v.hdr?.scl_inter || 0;
      const NB = 128, counts = new Float64Array(NB);
      const stride = Math.max(1, Math.floor(img.length / 400000));  // sample large volumes
      for (let i = 0; i < img.length; i += stride) {
        let x = img[i] * slope + inter;
        if (magnitude) x = Math.abs(x);
        if (!isFinite(x) || x === 0 || x < vmin || x > vmax) continue;  // only voxels in the zoom view
        counts[Math.min(NB - 1, Math.max(0, Math.floor(((x - vmin) / (vmax - vmin)) * NB)))]++;
      }
      let max = 0;
      for (let b = 0; b < NB; b++) { counts[b] = Math.log1p(counts[b]); if (counts[b] > max) max = counts[b]; }
      if (max > 0) { for (let b = 0; b < NB; b++) counts[b] /= max; hist = counts; }
    }
    draw();
  }
  function draw() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    const dpr = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    if (!hist) return;
    const dark = document.documentElement.classList.contains("dark");
    const px = (x) => ((x - vmin) / (vmax - vmin || 1)) * w;
    const loX = px(winLo), hiX = px(winHi);
    const NB = hist.length, bw = w / NB;
    for (let b = 0; b < NB; b++) {
      const bh = hist[b] * (h - 1);
      if (!bh) continue;
      const x = b * bw, mid = x + bw / 2;
      ctx.fillStyle = mid >= loX && mid <= hiX ? (dark ? "#818cf8" : "#6366f1") : (dark ? "#4b5563" : "#d1d5db");
      ctx.fillRect(x + 0.5, h - bh, Math.max(bw - 1, 0.75), bh);
    }
  }
  // Slider drag moves only the dragged bound, so a typed out-of-range bound on the other side survives.
  const onRange = (e) => {
    const x = parseFloat(e.target.value);
    const [lo, hi] = e.target === rngLo ? [x, winHi] : [winLo, x];
    apply(Math.min(lo, hi), Math.max(lo, hi));
  };
  rngLo.addEventListener("input", onRange);
  rngHi.addEventListener("input", onRange);
  // The value bubbles are editable: click to type an exact bound (out-of-range allowed). On focus show the
  // full-precision value and select it; Enter/blur commits, Escape reverts.
  const bubVal = (b) => (b === bubLo ? winLo : winHi);
  for (const b of [bubLo, bubHi]) {
    b.addEventListener("focus", () => {
      b.textContent = fmtNum(bubVal(b));
      const r = document.createRange(); r.selectNodeContents(b);
      const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
    });
    b.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); b.blur(); }
      else if (e.key === "Escape") { e.preventDefault(); b.textContent = fmtWin(bubVal(b)); b.blur(); }
    });
    b.addEventListener("blur", () => {
      const v = parseFloat(b.textContent);
      apply(b === bubLo ? v : winLo, b === bubHi ? v : winHi);  // apply() handles NaN + lo/hi order
    });
  }
  q(".btn-auto").addEventListener("click", () => { const v = getVol(); if (!v) return; autoWin(v); apply(v.cal_min, v.cal_max); });
  // Scroll to zoom the view about the cursor (finer control in a narrow range); double-click resets.
  dr.addEventListener("wheel", (e) => {
    if (!getVol()) return;
    e.preventDefault();
    const rect = dr.getBoundingClientRect();
    const frac = rect.width ? Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)) : 0.5;
    zoom(e.deltaY < 0 ? 0.8 : 1.25, frac);
  }, { passive: false });
  dr.addEventListener("dblclick", () => { if (!getVol()) return; vmin = dmin; vmax = dmax; applyView(); });

  const ctl = { el, setup, redraw: () => { draw(); positionBubbles(); }, setMagnitude: (on) => { magnitude = on; }, cmapSelect: cmapSel };
  winControls.push(ctl);
  return ctl;
}

function wireControls() {
  // base map colormap (recon/truth) — compact dropdown above this control's Auto button
  baseCtl = makeWindowControl(() => nv.volumes[0], {
    value: "gray",
    options: [["gray", "Gray"], ["viridis", "Viridis"], ["plasma", "Plasma"], ["hot", "Hot"], ["cool", "Cool"]],
    onChange: (v) => { const vol = baseVol(); if (vol) { vol.colormap = v; nv.updateGLVolume(); } },
  });
  // error overlay colormap — dropdown above the error window's Auto button; drives setErrorColormap
  errorCtl = makeWindowControl(() => nv.volumes[1], {
    value: "diverging",
    options: [["diverging", "Diverging (red ↔ blue)"], ["warm", "Warm"], ["hot", "Hot"], ["viridis", "Viridis"], ["plasma", "Plasma"], ["cool", "Cool"], ["gray", "Gray"]],
    onChange: () => setErrorColormap(),
  });
  $("win-base").appendChild(baseCtl.el);
  $("win-error").appendChild(errorCtl.el);

  $("layer-tabs").querySelectorAll("button").forEach((t) =>
    t.addEventListener("click", () => { curBase = t.dataset.layer; setLayerActive(curBase); refreshView(); }));
  $("t-error").addEventListener("change", (e) => { showError = e.target.checked; refreshView(); });
  $("view-tabs").querySelectorAll("button").forEach((t) =>
    t.addEventListener("click", () => { setViewActive(t.dataset.view); nv.setSliceType(nv["sliceType" + cap(t.dataset.view)]); }));
  $("t-colorbar").addEventListener("change", (e) => { nv.opts.isColorbar = e.target.checked; nv.drawScene(); });
  $("t-crosshair").addEventListener("change", (e) => { nv.setCrosshairWidth(e.target.checked ? 0.75 : 0); });
  $("t-interp").addEventListener("change", (e) => { nv.setInterpolation(!e.target.checked); nv.drawScene(); });
  $("opacity").addEventListener("input", (e) => {
    const o = parseFloat(e.target.value);
    for (let i = 1; i < nv.volumes.length; i++) nv.setOpacity(i, o);
    $("opacity-val").textContent = Math.round(o * 100) + "%";
    nv.updateGLVolume();
  });
  const redrawAll = () => winControls.forEach((c) => c.redraw());
  window.addEventListener("resize", redrawAll);
  // theme toggle flips html.dark without reloading — recolour every histogram
  new MutationObserver(redrawAll).observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  nv.setInterpolation(true);
  setViewActive("multiplanar");
}

// Volumes are served from the Hugging Face Hub (run.volumes[kind]); fall back to local results/<id>/ for dev.
const volUrl = (kind) => (run && run.volumes && run.volumes[kind]) || (baseUrl + kind + ".nii.gz");

// Reconcile the viewer with (curBase, showError): reload the base only when it changes, add/remove the
// error overlay independently, and show a second windowing section for the error map when it's on.
async function refreshView() {
  const cmap = baseCtl.cmapSelect.value;
  const baseKind = curBase === "truth" ? "truth" : "recon";
  const needBase = loadedBase !== baseKind || !nv.volumes.length;
  if (needBase || (showError && !loadedError)) setLoading(true);  // only when a fetch is actually pending
  try {
    if (needBase) {
      await nv.loadVolumes([{ url: volUrl(baseKind), colormap: cmap }]);  // replaces all volumes (drops any overlay)
      defaultWindow(baseVol());
      loadedBase = baseKind; loadedError = false;
      baseCtl.setup();
    }
    if (showError && !loadedError) {
      await nv.addVolumeFromUrl({ url: volUrl("error"), opacity: parseFloat($("opacity").value) });
      loadedError = true;
      setErrorColormap();  // sets colormap (+ diverging negative), window, magnitude mode and label
    } else if (!showError && loadedError) {
      nv.removeVolumeByUrl(volUrl("error"));
      loadedError = false;
    }
  } finally { setLoading(false); }
  nv.updateGLVolume();
  $("win-error-section").classList.toggle("hidden", !showError);
}

// Apply the chosen error-overlay colormap. The error is always windowed on |error| (magnitude) with a
// transparency floor: cal_min hides near-zero background, cal_max saturates, both mirrored to the
// negative side. χ error uses the eval's ppm scale (floor 0.01, sat 0.1 ppm).
function setErrorColormap() {
  if (!loadedError) return;
  const ov = nv.volumes[nv.volumes.length - 1];
  const cfg = ERROR_CMAPS[errorCtl.cmapSelect.value] || ERROR_CMAPS.diverging;
  ov.colormap = cfg.colormap;
  ov.colormapNegative = cfg.colormapNegative;
  if (run.kind === "chi") { ov.cal_min = 0.01; ov.cal_max = 0.1; }
  else {
    const m = Math.max(Math.abs(ov.robust_min ?? ov.global_min), Math.abs(ov.robust_max ?? ov.global_max)) || 1;
    ov.cal_min = 0.02 * m; ov.cal_max = m;
  }
  errorCtl.setMagnitude(true);
  errorCtl.setup();
  nv.updateGLVolume();
}

// ---- boot -------------------------------------------------------------------
async function init() {
  [allRuns, algos, registry] = await Promise.all([loadRuns(), loadAlgos(), loadRegistry()]);
  // Accept ?run=<run-id> (e.g. ismv-iso), or a bare slug via ?run= / ?method= (e.g. ?method=ismv,
  // the form Zenodo records link to) → resolve to that algorithm's isolated run.
  const q = new URLSearchParams(location.search);
  const want = q.get("run") || q.get("method");
  run = allRuns.find((r) => r.id === want)
    || allRuns.find((r) => r.mode === "isolated" && r.slug === want)
    || allRuns.find((r) => r.status !== "DNF") || allRuns[0];
  if (!run) { $("sub-title").textContent = "No runs"; return; }
  navMode = run.mode === "composed" ? "pipelines" : "stages";
  $("run-filter").addEventListener("input", (e) => { filter = e.target.value; buildSidebar(); });
  document.querySelectorAll("#nav-toggle button").forEach((b) => b.addEventListener("click", () => { navMode = b.dataset.mode; buildSidebar(); }));
  // Deep links: ?layer=truth selects the ground-truth base; ?layer=error (or ?error=1) turns on the
  // error overlay. Applied before the first render so loadRun picks them up.
  const layer = q.get("layer");
  if (layer === "truth") curBase = "truth";
  if (layer === "error" || q.get("error") === "1") showError = true;
  buildSidebar();
  await loadRun();
}
init();
