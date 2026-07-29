// Submission detail + NiiVue viewer: run sidebar, in-place switching, cohesive controls,
// histogram-backed dual-range windowing with typed bounds, and per-algorithm docs.
// Module scope; helpers via window.QSM. The resource chart and the dual-range windowing widget live
// in their own modules (resourceChart.js / windowControl.js) — this file coordinates them.
import { Niivue } from "https://unpkg.com/@niivue/niivue@0.57.0/dist/index.js";
import { renderResources } from "./resourceChart.js";
import { makeWindowControl, winControls } from "./windowControl.js";

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
  // χ-separation produces TWO source maps, so `produces` is an array — runLine writes them to a
  // directory and scores against a ground-truth directory.
  "chi-separation": { consumes: ["localfield", "r2prime", "chimap", "magnitude", "mask", "params"],
    produces: ["chi-para", "chi-dia"] },
};
const ARTFILE = { phase: "phase.nii.gz", magnitude: "magnitude.nii.gz", mask: "mask.nii.gz",
  params: "params.json", totalfield: "totalfield.nii.gz", localfield: "localfield.nii.gz",
  chimap: "chimap.nii.gz", r2prime: "r2prime.nii.gz", "chi-para": "chi-para.nii.gz",
  "chi-dia": "chi-dia.nii.gz" };
const escapeHtml = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

function runLine(slug, stage, truth, inputs) {
  const io = STAGE_IO[stage];
  if (!io) return `qsm-ci run ${slug}`;
  // Prefer the method's declared inputs (only the artifacts it actually reads) so the command doesn't
  // advertise flags the method ignores; fall back to the stage's full consumes when a run predates the
  // manifest field. One flag per line, backslash-continued, so long commands don't overflow the block.
  const consumes = (inputs && inputs.length ? inputs.filter((a) => ARTFILE[a]) : io.consumes);
  const parts = [`qsm-ci run ${slug}`, ...consumes.map((a) => `--${a} ${ARTFILE[a]}`)];
  if (Array.isArray(io.produces)) {  // multi-output (χ-separation): a directory in, a directory to score against
    parts.push("-o out/");
    if (truth) parts.push("--truth groundtruth/");
  } else {
    parts.push(`-o ${ARTFILE[io.produces]}`);
    if (truth) parts.push(`--truth ${io.produces}_groundtruth.nii.gz`);
  }
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
    const ins = (s) => bySlug[s] && bySlug[s].inputs;
    if (fm && fm !== "gt" && stageOf(fm)) lines.push(runLine(fm, stageOf(fm), false, ins(fm)));
    if (bfr && stageOf(bfr)) lines.push(runLine(bfr, stageOf(bfr), false, ins(bfr)));
    if (dipole && stageOf(dipole)) lines.push(runLine(dipole, stageOf(dipole), true, ins(dipole)));
  } else if (bySlug[run.slug]) {
    lines.push(runLine(run.slug, run.stage, true, bySlug[run.slug].inputs));
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
let nv = null, run, baseUrl, filter = "", navMode = "stages", domain = "qsm";
let curBase = "recon";       // base map shown underneath: recon | truth
let chisepComp = "para";     // χ-separation source shown: para (χ+) | dia (χ−)
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
// χ-separation methods (a distinct domain): one flat list, default variant only.
const chisepRuns = () => allRuns.filter((r) => (r.domain === "chisep" || r.stage === "chi-separation")
  && (r.variant || "default") === "default");
const hasChisep = () => chisepRuns().length > 0;
// Combined single-step methods (bfr+dipole / end-to-end, e.g. NeXtQSM/TGV/QSMART/MEDI/iQSM) go
// straight to a chi map in one step, so they have no fmap×bfr×dipole combo and are missed by the
// matrix axes. Surface them as their own Pipelines group — one run per slug, preferring the composed
// representation. (unwrap+bfr methods produce localfield, not chi, so they sit on the matrix's
// background-removal axis instead and are excluded here.)
const combinedRuns = () => {
  const bySlug = {};
  for (const r of allRuns) {
    if (r.combo) continue;  // matrix combos carry stage bfr+dipole too — they belong on the axes
    if (r.variant === "tuned") continue;  // tuned variants are reached via the toggle, not the list
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
  // χ-separation rows carry no plain xsim — show the mean of the χ+ and χ− xSIM instead.
  const m = (r && r.metrics) || {};
  const xs = m.xsim != null ? m.xsim
    : (m.para_xsim != null && m.dia_xsim != null ? (m.para_xsim + m.dia_xsim) / 2
    : (r ? val(r, "xsim") : null));
  const label = r ? (r.status === "DNF" ? "DNF" : fmt(xs, "xsim")) : "—";
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
    const rs = allRuns.filter((r) => r.mode === "isolated" && r.stage === s && (r.variant || "default") === "default" && (!f || r.name.toLowerCase().includes(f)));
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
function chisepHTML() {
  const f = filter.toLowerCase();
  const rs = chisepRuns().filter((r) => !f || r.name.toLowerCase().includes(f));
  if (!rs.length) return `<p class="p-3 text-sm text-gray-400">No χ-separation methods yet.</p>`;
  const rows = rs.map((r) => runItem(r, run?.id).replace("%NAME%", r.name)).join("");
  return `<div class="mb-3"><div class="px-2.5 pt-1 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">χ-separation</div>${rows}</div>`;
}
function buildSidebar() {
  if (domain === "chisep" && !hasChisep()) domain = "qsm";
  // Domain toggle: the χ-separation button is present only when such methods exist.
  document.querySelectorAll("#domain-toggle button").forEach((b) =>
    b.className = "flex-1 rounded-md px-2 py-1 transition "
      + (b.dataset.domain === "chisep" && !hasChisep() ? "hidden " : "")
      + (b.dataset.domain === domain ? "bg-white shadow-sm text-gray-900 dark:bg-gray-700 dark:text-gray-100" : "text-gray-500 hover:text-gray-700 dark:text-gray-400"));
  // The Stages/Pipelines split is meaningless for χ-separation (one flat list) — hide it there.
  $("nav-toggle")?.classList.toggle("hidden", domain === "chisep");
  document.querySelectorAll("#nav-toggle button").forEach((b) =>
    b.className = "flex-1 rounded-md px-2 py-1 transition " +
      (b.dataset.mode === navMode ? "bg-white shadow-sm text-gray-900 dark:bg-gray-700 dark:text-gray-100" : "text-gray-500 hover:text-gray-700 dark:text-gray-400"));
  $("run-list").innerHTML = domain === "chisep" ? chisepHTML() : (navMode === "stages" ? stagesHTML() : pipelinesHTML());
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
  // A parameter may carry a `tuned:` value — the setting optimised on the QSM-CI scoring phantom,
  // shown next to the method's usual `default:`. Only disclosed (submission page); the leaderboard
  // still ranks methods at their defaults.
  const plist = a.parameters || [];
  const hasTuned = plist.some((p) => p.tuned != null && String(p.tuned) !== String(p.default));
  const params = plist.map((p) => {
    const tuned = (p.tuned != null && String(p.tuned) !== String(p.default))
      ? `<span class="text-emerald-600 dark:text-emerald-400" title="Optimised on the QSM-CI scoring phantom">⚙ ${p.tuned}</span>`
      : `<span class="text-gray-300 dark:text-gray-600">—</span>`;
    return `<tr class="border-t border-gray-100 dark:border-gray-800"><td class="py-1 pr-3 font-mono text-gray-700 dark:text-gray-300">${p.name}</td><td class="py-1 pr-3 tabular-nums text-gray-500 dark:text-gray-400">${p.default}</td>${hasTuned ? `<td class="py-1 pr-3 tabular-nums">${tuned}</td>` : ""}<td class="py-1 text-gray-400 dark:text-gray-500">${p.description || ""}</td></tr>`;
  }).join("");
  const paramHead = hasTuned
    ? `<thead><tr class="text-left text-gray-400 dark:text-gray-500"><th class="py-1 pr-3 font-normal">parameter</th><th class="py-1 pr-3 font-normal">default</th><th class="py-1 pr-3 font-normal"><span class="has-tip text-emerald-600 dark:text-emerald-400" data-tip="Value optimised on the QSM-CI scoring phantom (maximising xSIM). The default is the method's usual setting; the leaderboard still ranks methods at their defaults.">⚙ tuned</span></th><th class="py-1 font-normal"></th></tr></thead>`
    : "";
  return `<div>
    <div class="flex items-baseline gap-2">
      <span class="font-medium text-gray-900 dark:text-gray-100">${a.name}</span>
      <span class="text-xs text-gray-400">${a.stage ? (STAGE_LABEL[a.stage] || a.stage) : ""}</span>
    </div>
    <p class="mt-0.5 text-sm text-gray-600 dark:text-gray-400">${a.description || ""}</p>
    ${(a.ci_notes && a.ci_notes.length) ? `<div class="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
      <div class="flex items-center gap-1.5 font-semibold"><span aria-hidden="true">⚠</span> How QSM-CI runs this</div>
      <ul class="mt-1 list-disc space-y-0.5 pl-4 marker:text-amber-400">${a.ci_notes.map((n) => `<li>${n}</li>`).join("")}</ul>
    </div>` : ""}
    ${params ? `<table class="mt-2 w-full text-xs">${paramHead}<tbody>${params}</tbody></table>` : ""}
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
// Default + tuned isolated runs for the current method, if both exist (drives the Defaults/Tuned
// toggle — switching swaps the metrics AND the NiiVue volumes, since each variant is its own run).
function variantRuns() {
  if (!run || run.mode !== "isolated") return null;
  const sib = allRuns.filter((r) => r.slug === run.slug && r.mode === "isolated" && r.artifact === run.artifact);
  const def = sib.find((r) => (r.variant || "default") === "default");
  const tun = sib.find((r) => r.variant === "tuned" && r.status !== "DNF");
  return def && tun ? { def, tun } : null;
}
function variantToggleHTML() {
  const v = variantRuns();
  if (!v) return "";
  const cur = run.variant === "tuned" ? "tuned" : "default";
  const btn = (key, id, label) =>
    `<button data-variant-id="${id}" class="px-2 py-0.5 rounded-md transition ${cur === key
      ? "bg-white shadow-sm text-emerald-700 dark:bg-gray-700 dark:text-emerald-400"
      : "text-gray-500 hover:text-gray-700 dark:text-gray-400"}">${label}</button>`;
  return `<span class="inline-flex items-center rounded-lg bg-gray-100 dark:bg-gray-800 p-0.5 text-xs font-medium align-middle"
    title="Switch between the method's default parameters and the values optimised on the QSM-CI scoring phantom. Metrics and the volumes below update to match.">${btn("default", v.def.id, "Defaults")}${btn("tuned", v.tun.id, "⚙ Tuned")}</span>`;
}

async function loadRun() {
  $("sub-title").textContent = run.name;
  const stageCls = STAGE_COLOR[run.stage] || "bg-gray-100 text-gray-600 ring-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:ring-gray-700";
  $("sub-badges").innerHTML =
    badge(STAGE_LABEL[run.stage] || run.stage, stageCls) +
    badge(run.mode === "composed" ? "Composed pipeline" : "Isolated", "bg-gray-100 text-gray-600 ring-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:ring-gray-700") +
    (run.status === "DNF" ? badge("DNF", "bg-red-50 text-red-600 ring-red-100 dark:bg-red-500/10 dark:text-red-400 dark:ring-red-500/20") : "") +
    variantToggleHTML();
  $("sub-badges").querySelectorAll("[data-variant-id]").forEach((b) =>
    b.addEventListener("click", () => selectRun(b.dataset.variantId)));
  const bits = [];
  if (run.artifact) bits.push(`scored artifact <code class="text-gray-700 dark:text-gray-300">${run.artifact}</code>`);
  if (run.image) bits.push(`image <code class="text-gray-700 dark:text-gray-300">${run.image}</code>`);
  $("sub-meta").innerHTML = bits.join(" · ");
  renderMethodInfo();
  renderHowToRun();
  renderMetrics();
  // Render the resource graph up front — independent of (and before) the WebGL/NiiVue viewer, so a
  // browser without WebGL2, or a run whose volumes fail to load, still shows the usage trace.
  renderResources(run);

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
    nv.addColormap("errpos", ERR_POS_CMAP);   // signed error map: over-estimate (red), under-estimate (blue)
    nv.addColormap("errneg", ERR_NEG_CMAP);
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
  // χ-separation runs get a χ+ / χ− source toggle; other runs hide it.
  $("chisep-tabs").classList.toggle("hidden", !isChisepRun());
  if (isChisepRun()) setChisepActive(chisepComp);
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
  const meta = METRICS[k], v = val(run, k);   // val() also reaches top-level fields (e.g. runtime_s)
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

function renderChisepMetrics() {
  // χ-separation runs carry paired, source-specific metrics (para_*/dia_*), not the plain QSM keys.
  // Render them grouped by source: χ+ gets iron/vein metrics, χ− gets calcification metrics, and each
  // gets a leakage (cross-contamination) term.
  $("metrics-sub").textContent = "χ+ / χ− sources vs. ground truth";
  const m = run.metrics || {};
  const avg = (m.para_xsim != null && m.dia_xsim != null) ? (m.para_xsim + m.dia_xsim) / 2 : null;
  const num = (v, fk) => v == null ? null
    : fk === "pct" ? v.toFixed(1) + "%" : fk === "xsim" ? fmt(v, "xsim")
    : fk === "sec" ? fmt(v, "runtime_s") : v.toFixed(3);
  const groups = [
    [null, [["Avg xSIM", avg, "xsim", "↑", "Mean of the χ+ and χ− xSIM — the headline combined score."]]],
    ["χ+ paramagnetic (iron, veins)", [
      ["xSIM", m.para_xsim, "xsim", "↑", "Structural similarity of χ+ vs ground truth."],
      ["NRMSE", m.para_nrmse, "pct", "↓", "Normalised RMS error of χ+ (%)."],
      ["DGM iron NRMSE", m.para_nrmse_dgm, "pct", "↓", "χ+ error in deep gray matter (iron)."],
      ["DGM linearity", m.para_dgm_linearity, "num", "↓", "|1 − slope| of χ+ across DGM iron regions; 0 = perfect iron quantification."],
      ["Vein NRMSE", m.para_nrmse_blood, "pct", "↓", "χ+ error in venous blood."],
      ["Calcium leakage", m.para_calc_leak, "num", "↓", "Mean |χ+| in the calcification (should be ~0) — calcium wrongly bleeding into the paramagnetic map."],
    ]],
    ["χ− diamagnetic (calcium, myelin)", [
      ["xSIM", m.dia_xsim, "xsim", "↑", "Structural similarity of χ− vs ground truth."],
      ["NRMSE", m.dia_nrmse, "pct", "↓", "Normalised RMS error of χ− (%)."],
      ["Calcification dev", m.dia_calc_moment_dev, "num", "↓", "Deviation of the recovered calcification's susceptibility moment."],
      ["Streaking", m.dia_calc_streak, "num", "↓", "Streaking-artifact level around the calcification."],
      ["Iron leakage", m.dia_iron_leak, "num", "↓", "Mean |χ−| in DGM/veins (should be ~0) — iron wrongly bleeding into the diamagnetic map."],
    ]],
    [null, [["Runtime", run.runtime_s, "sec", "", "Wall-clock runtime."]]],
  ];
  let html = "";
  for (const [header, rows] of groups) {
    if (header) html += `<tr><td colspan="3" class="pt-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">${header}</td></tr>`;
    for (const [label, v, fk, arrow, tip] of rows) {
      if (v == null) continue;
      const hero = label === "Avg xSIM";
      html += `<tr>
        <td class="py-2 text-gray-500 dark:text-gray-400"><span class="has-tip" data-tip="${tip.replace(/"/g, "&quot;")}">${label}</span> <span class="text-gray-300 dark:text-gray-600" title="${arrow === "↑" ? "higher" : "lower"} is better">${arrow}</span></td>
        <td class="py-2 text-right tabular-nums ${hero ? "font-bold text-gray-900 dark:text-gray-100" : "font-medium text-gray-700 dark:text-gray-300"}">${num(v, fk)}</td>
        <td class="py-2 pl-3 text-right"><span class="text-gray-300 dark:text-gray-600">—</span></td>
      </tr>`;
    }
  }
  $("metrics-body").innerHTML = html || `<tr><td class="py-3 text-gray-400">No metrics for this run.</td></tr>`;
}
function renderMetrics() {
  if (run.domain === "chisep" || run.stage === "chi-separation") { renderChisepMetrics(); return; }
  $("metrics-sub").textContent = run.mode === "composed" ? "Final χ map vs. ground truth" : `${run.artifact || "output"} vs. ground truth`;
  // Include runtime_s (a top-level field, not under run.metrics) via val(), so it's ranked alongside
  // the accuracy metrics. Object.keys(METRICS) keeps it last, matching its registry order.
  const order = Object.keys(METRICS).filter((k) => val(run, k) != null);
  const groupLabel = run.combo ? "composed pipelines" : `isolated ${STAGE_LABEL[run.stage] || run.stage} methods`;
  $("metrics-body").innerHTML = order.map((k) => {
    const meta = METRICS[k], arrow = meta.better === "higher" ? "↑" : "↓", hero = k === "xsim" || k === "nrmse";
    const rk = metricRank(k);
    const rankCell = rk
      ? `<span class="inline-block rounded-md px-1.5 py-0.5 text-xs font-semibold text-white shadow-sm" style="background:${heatScale(rk.t)}" data-tip="Rank ${rk.rank} of ${rk.n} ${groupLabel} for ${meta.label}">#${rk.rank}<span class="opacity-70"> / ${rk.n}</span></span>`
      : `<span class="text-gray-300 dark:text-gray-600">—</span>`;
    return `<tr>
      <td class="py-2.5 text-gray-500 dark:text-gray-400"><span class="has-tip" data-tip="${(meta.desc || "").replace(/"/g, "&quot;")}">${meta.label}</span> <span class="text-gray-300 dark:text-gray-600" title="${meta.better} is better">${arrow}</span></td>
      <td class="py-2.5 text-right tabular-nums ${hero ? "font-bold text-gray-900 dark:text-gray-100" : "font-medium text-gray-700 dark:text-gray-300"}">${fmt(val(run, k), k)}</td>
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
function setChisepActive(comp) {
  $("chisep-tabs").querySelectorAll("button").forEach((t) =>
    t.className = "rounded-md px-3 py-1 transition " +
      (t.dataset.comp === comp ? "bg-white shadow-sm text-gray-900 dark:bg-gray-700 dark:text-gray-100" : "text-gray-500 hover:text-gray-700 dark:text-gray-400"));
}
function setViewActive(v) {
  $("view-tabs").querySelectorAll("button").forEach((b) =>
    b.className = "rounded-md px-2.5 py-1 transition " +
      (b.dataset.view === v ? "bg-indigo-600 text-white dark:bg-indigo-500" : "text-gray-500 hover:text-gray-700 dark:text-gray-400"));
}
function autoWin(vol) { vol.cal_min = vol.robust_min ?? vol.global_min; vol.cal_max = vol.robust_max ?? vol.global_max; }
function defaultWindow(vol) {
  if (run.kind === "chi") { vol.cal_min = -0.1; vol.cal_max = 0.1; }  // χ maps: fixed ±0.1 ppm
  // χ-separation sources are non-negative magnitudes: χ+ (paramagnetic) [0, 0.1], χ− (diamagnetic)
  // [0, 0.05]. The histogram auto-frames this window (~50% of view), matching the QSM behaviour.
  else if (isChisepRun()) { vol.cal_min = 0; vol.cal_max = chisepComp === "dia" ? 0.05 : 0.1; }
  else autoWin(vol);                                                  // fields / everything else: auto
}

// Signed error-map colormaps: over-estimate (recon>truth) ramps transparent→red→yellow, under-estimate
// ramps transparent→blue→cyan. Alpha starts at 0 so the inner window bound (cal_min) is a hard
// transparency floor — errors below it (incl. exact zero + the masked background) don't render at all —
// and rises to full by the outer bound (cal_max = saturation). Used as colormap / colormapNegative,
// so the two signs diverge from a fixed, transparent zero: the window changes only the ±inner/±outer
// thresholds, never the centre.
const ERR_POS_CMAP = { R: [180, 240, 255], G: [0, 70, 224], B: [0, 30, 40], A: [0, 200, 255], I: [0, 128, 255] };
const ERR_NEG_CMAP = { R: [0, 20, 120], G: [0, 90, 224], B: [140, 210, 255], A: [0, 200, 255], I: [0, 128, 255] };

// Colormaps for the error overlay. "diverging" is the zero-centered signed view (red = over, blue =
// under) with a transparency floor at cal_min and saturation at cal_max. The rest window on |error|
// with a single map for both signs (magnitude only).
const ERROR_CMAPS = {
  diverging: { colormap: "errpos", colormapNegative: "errneg" },  // signed: red = recon>truth, blue = recon<truth
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

function wireControls() {
  // base map colormap (recon/truth) — compact dropdown above this control's Auto button
  baseCtl = makeWindowControl(() => nv, () => nv.volumes[0], {
    value: "gray",
    options: [["gray", "Gray"], ["viridis", "Viridis"], ["plasma", "Plasma"], ["hot", "Hot"], ["cool", "Cool"]],
    onChange: (v) => { const vol = baseVol(); if (vol) { vol.colormap = v; nv.updateGLVolume(); } },
  });
  // error overlay colormap — dropdown above the error window's Auto button; drives setErrorColormap
  errorCtl = makeWindowControl(() => nv, () => nv.volumes[1], {
    value: "diverging",
    options: [["diverging", "Diverging (red ↔ blue)"], ["warm", "Warm"], ["hot", "Hot"], ["viridis", "Viridis"], ["plasma", "Plasma"], ["cool", "Cool"], ["gray", "Gray"]],
    onChange: () => setErrorColormap(),
  });
  $("win-base").appendChild(baseCtl.el);
  $("win-error").appendChild(errorCtl.el);

  $("layer-tabs").querySelectorAll("button").forEach((t) =>
    t.addEventListener("click", () => { curBase = t.dataset.layer; setLayerActive(curBase); refreshView(); }));
  // χ+ / χ− source toggle: switch which volume set loads, forcing a base reload (the URL changes but
  // the recon/truth kind doesn't, so refreshView wouldn't otherwise re-fetch).
  $("chisep-tabs").querySelectorAll("button").forEach((t) =>
    t.addEventListener("click", () => {
      chisepComp = t.dataset.comp; setChisepActive(chisepComp);
      loadedBase = null; loadedError = false; refreshView();
    }));
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
const isChisepRun = () => run && (run.domain === "chisep" || run.stage === "chi-separation");
// χ-separation writes a second set of volumes for the χ− source with a "-dia" suffix
// (recon-dia.nii.gz, truth-dia.nii.gz, error-dia.nii.gz); the χ+ set uses the plain names.
const volUrl = (kind) => {
  // Apply the χ− "-dia" suffix to the KEY too, not just the dev-fallback path — otherwise an
  // HF-backed run returns run.volumes["recon"] (the χ+ volume) for the χ− toggle.
  const suffix = (isChisepRun() && chisepComp === "dia") ? "-dia" : "";
  const k = kind + suffix;
  if (run && run.volumes && run.volumes[k]) return run.volumes[k];
  return baseUrl + k + ".nii.gz";
};

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
    // Reveal the error windowing section BEFORE setErrorColormap() so its canvas has a non-zero size
    // when the histogram first draws — otherwise it renders blank and the bubbles mis-position until
    // the next interaction (a hidden `display:none` element reports clientWidth 0).
    $("win-error-section").classList.toggle("hidden", !showError);
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
  // Window on |error|, mirrored to both signs so zero is a fixed, transparent centre. cal_min = inner
  // (transparency floor — errors below it, including exact zero, don't render); cal_max = outer
  // (saturation — beyond it everything shows the top colour). Moving either changes only the ±inner/
  // ±outer thresholds, never where the two signs diverge.
  const m = (run.kind === "chi") ? 0.1
    : (Math.max(Math.abs(ov.robust_min ?? ov.global_min), Math.abs(ov.robust_max ?? ov.global_max)) || 1);
  ov.cal_min = (run.kind === "chi") ? 0.02 : 0.05 * m;
  ov.cal_max = m;
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
  domain = (run.domain === "chisep" || run.stage === "chi-separation") ? "chisep" : "qsm";
  navMode = run.mode === "composed" ? "pipelines" : "stages";
  $("run-filter").addEventListener("input", (e) => { filter = e.target.value; buildSidebar(); });
  document.querySelectorAll("#nav-toggle button").forEach((b) => b.addEventListener("click", () => { navMode = b.dataset.mode; buildSidebar(); }));
  document.querySelectorAll("#domain-toggle button").forEach((b) => b.addEventListener("click", () => { domain = b.dataset.domain; buildSidebar(); }));
  // Deep links: ?layer=truth selects the ground-truth base; ?layer=error (or ?error=1) turns on the
  // error overlay. Applied before the first render so loadRun picks them up.
  const layer = q.get("layer");
  if (layer === "truth") curBase = "truth";
  if (layer === "error" || q.get("error") === "1") showError = true;
  buildSidebar();
  await loadRun();
}
init();
