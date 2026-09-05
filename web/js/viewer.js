// Submission detail + NiiVue viewer: run sidebar, in-place switching, cohesive controls,
// histogram-backed dual-range windowing with typed bounds, and per-algorithm docs.
// Module scope; helpers via window.QSM. The resource chart and the dual-range windowing widget live
// in their own modules (resourceChart.js / windowControl.js); this file coordinates them.
import { Niivue } from "https://unpkg.com/@niivue/niivue@0.57.0/dist/index.js";
import { renderResources } from "./resourceChart.js";
import { makeWindowControl, winControls } from "./windowControl.js";

const { loadRuns, loadAlgos, loadDatasets, loadRegistry, loadRunRegions, doiFor, METRICS, STAGE_LABEL, val, fmt, robustRange, heatScale } = window.QSM;

const STAGE_COLOR = {
  "field-mapping": "bg-indigo-50 text-indigo-700 ring-indigo-100 dark:bg-indigo-500/10 dark:text-indigo-300 dark:ring-indigo-500/20",
  bfr: "bg-violet-50 text-violet-700 ring-violet-100 dark:bg-violet-500/10 dark:text-violet-300 dark:ring-violet-500/20",
  dipole: "bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-100 dark:bg-fuchsia-500/10 dark:text-fuchsia-300 dark:ring-fuchsia-500/20",
};

// Which dataset a run was scored on, shown as the leading badge on the detail page so an in-vivo
// (2016) run is never mistaken for an in-silico (2019) one. Amber for in-vivo matches results.html.
const DATASET_BADGE = {
  qsm:    ["In silico (2019)", "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/20"],
  chisep: ["χ-separation",     "bg-indigo-50 text-indigo-700 ring-indigo-200 dark:bg-indigo-500/10 dark:text-indigo-300 dark:ring-indigo-500/20"],
  invivo: ["In vivo (2016)",   "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/20"],
  repro:  ["Harmonization (2026)", "bg-sky-50 text-sky-700 ring-sky-200 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-500/20"],
};

// ── Harmonization (repro) dataset ──────────────────────────────────────────────────────────────
// The repro track is a first-class dataset here: for the current acquisition we synthesise one
// composed-run object per pipeline (from repro.json) and splice them into allRuns, so the SAME
// pipelines sidebar / selectRun / method-card machinery renders it exactly like in-silico. There's
// no ground truth, so those runs are recon-only (χ map streamed from the deterministic HF path
// repro/<acq>/<pipeline>-cmp-<acq>__recon.nii.gz) and carry reproducibility stats instead of accuracy
// metrics. The scanner/protocol/run pickers just regenerate the pool for a different acquisition.
const HF_VOL_BASE = "https://huggingface.co/datasets/qsmxt/qsm-ci-volumes/resolve/main/";
let reproMode = false, reproPipe = "", reproAcq = "", reproJson = null;
const reproReconUrl = (pipe, acq) => `${HF_VOL_BASE}repro/${acq}/${pipe.replaceAll("+", "_")}-cmp-${acq}__recon.nii.gz`;
// The CPU/RAM sampling trace for this pipeline×acquisition, published to the Hub alongside the recon
// (same deterministic path). Carries the time series AND the peak-mem / avg-cpu / max-cpu summary.
const reproResourcesUrl = (pipe, acq) => `${HF_VOL_BASE}repro/${acq}/${pipe.replaceAll("+", "_")}-cmp-${acq}__resources.json`;
// Per-region susceptibility means for this pipeline×acquisition, published to the Hub alongside the
// recon (same deterministic path), powers the Regions tab. No ground truth on the repro track, so the
// file carries a `chi.recon` block only (no `truth`); a run whose regions file is absent just leaves the tab empty.
const reproRegionsUrl = (pipe, acq) => `${HF_VOL_BASE}repro/${acq}/${pipe.replaceAll("+", "_")}-cmp-${acq}__regions.json`;
// The RSS-combined multi-echo magnitude for this ACQUISITION (one per acq on the Hub, shared by every
// pipeline of it), the input structural reference the viewer's Magnitude layer shows next to the recon.
const reproMagnitudeUrl = (acq) => `${HF_VOL_BASE}repro/${acq}/${acq}__magnitude.nii.gz`;
// The two INTERMEDIATE maps of a harmonization pipeline, published next to the recon. Both are
// per-COLUMN artifacts, not per-pipeline: the total field belongs to the field-mapping method alone,
// and the local field to the (field-mapping, background-removal) pair — every pipeline built on that
// column streams the same file, which is why regenerating them costs 26 runs per acquisition rather
// than 660. A pipeline that skips a stage simply has no URL for it: a bfr+dipole span
// (romeo-qsmrs+tgv-qsmrs) has a field map but no local field, and an end-to-end method (iqsm) neither.
const reproTotalfieldUrl = (fm, acq) => `${HF_VOL_BASE}repro/${acq}/${fm}__totalfield.nii.gz`;
const reproLocalfieldUrl = (fm, bfr, acq) => `${HF_VOL_BASE}repro/${acq}/${fm}_${bfr}__localfield.nii.gz`;
const simRunIdOf = (pipe) => `${pipe.replaceAll("+", "~")}-cmp`;   // the same pipeline's in-silico composed run id
const reproRunId = (pipe, acq) => `${pipe.replaceAll("+", "~")}-cmp-${acq}`;
// Headline "score" for a repro run row: median inter-scanner |a-1| (lower is better).
const reproHeadline = (node) => node ? {
  repro_inter: node.inter_scanner_mean_abs_slope_dev,
  repro_tr: node.test_retest_mean_abs_slope_dev,
  repro_vsbridge: node.inter_protocol_mean_abs_slope_dev } : {};
function makeReproRun(pipe, acq, node) {
  // pipeline id parts = stages: 3 → field-mapping+bfr+dipole; 2 → field-mapping + a bfr+dipole span;
  // 1 → an end-to-end span. Matches how pipeline.py builds the combo, so the matrix axes line up.
  const parts = pipe.split("+");
  let combo = null, slug = pipe, stage = "end-to-end";
  if (parts.length === 3) { combo = { field_mapping: parts[0], bfr: parts[1], dipole: parts[2] }; stage = "field-mapping+bfr+dipole"; }
  // 2 parts = a field mapping method + a single span (bfr+dipole like QSMART/TGV/TFI, or end-to-end
  // like NeXtQSM/AutoQSM). There is no bfr/dipole pair to hang on the matrix axes, so leave `combo`
  // null and carry the span's OWN stage: that routes the row to the sidebar's combined-methods group
  // (spanRuns/spanSlugs) instead of the matrix, which would otherwise drop it from the dataset.
  // The field-mapping step is not lost — `pipelineId` still names the whole pipeline (pipelineSteps).
  else if (parts.length === 2) { slug = parts[1]; stage = algoStage(parts[1]) || "bfr+dipole"; }
  return { id: reproRunId(pipe, acq), slug, name: parts.map(algoName).join(" → "),
           pipelineId: pipe, track: "repro", phantom: acq, mode: "composed", stage, combo,
           kind: "chi",   // every harmonization pipeline outputs a susceptibility map → default window ±0.1 ppm
           status: "ok", metrics: reproHeadline(node),
           volumes: { recon: reproReconUrl(pipe, acq), magnitude: reproMagnitudeUrl(acq),
                      // parts[0] is the field-mapping stage (3- and 2-part pipelines); parts[1] is the
                      // background removal (3-part only). An end-to-end pipeline has neither.
                      ...(parts.length >= 2 ? { totalfield: reproTotalfieldUrl(parts[0], acq) } : {}),
                      ...(parts.length === 3 ? { localfield: reproLocalfieldUrl(parts[0], parts[1], acq) } : {}) },
           resources_url: reproResourcesUrl(pipe, acq), regions_url: reproRegionsUrl(pipe, acq) };
}
// (Re)generate the harmonization run pool for one acquisition and splice it into allRuns.
function ensureReproRuns(acq) {
  reproAcq = acq;
  allRuns = allRuns.filter((r) => r.track !== "repro");
  if (reproJson?.pipelines) for (const [pipe, node] of Object.entries(reproJson.pipelines)) allRuns.push(makeReproRun(pipe, acq, node));
}
// Fetch repro.json once (null = never tried, {} = tried-and-empty so we don't refetch forever). Loaded
// eagerly at boot so even a scored (in-silico) pipeline knows whether it has a harmonization analog.
async function ensureReproJson() {
  if (reproJson !== null) return reproJson;
  try { reproJson = await (await fetch("results/repro.json", { cache: "no-store" })).json(); }
  catch { reproJson = {}; }
  // Keep only pipelines whose every step is a live, visible method. The harvest (repro_eval.py) now
  // drops methods RETIRED from the manifest, so what's left to filter here are the ones deliberately
  // kept but hidden — a parked submission like the MATLAB amp-pe, whose data stays in repro.json so
  // it can be revived. loadRuns() applies the same rule to the in-silico runs, and skipping it
  // doesn't just show a parked method: it lets its rows bleed into the axes that cross it (every
  // background-removal row is a pipeline ending in the DEFAULT dipole method, so a parked default
  // blanks the whole axis). The retired case is still handled, for a payload written before this.
  if (algos.length && reproJson?.pipelines) reproJson.pipelines = Object.fromEntries(
    Object.entries(reproJson.pipelines).filter(([pipe]) => pipe.split("+").every(liveAlgo)));
  return reproJson;
}
const pipeHasRepro = (pipe) => !!reproJson?.pipelines?.[pipe];
const hasRepro = () => !!reproJson?.pipelines && Object.keys(reproJson.pipelines).length > 0;
// Enter the harmonization view IN-PLACE (no page navigation): make sure repro.json and the
// acquisition's run pool are loaded, then select `pipe`'s composed run there. `pipe` may be null (or
// a pipeline with no harmonization analog) when entering from an isolated run; fall back to the first
// available harmonization pipeline so the dataset tab is never a dead end.
async function enterRepro(pipe, acq) {
  await ensureReproJson();
  acq = acqExists(acq) ? acq : "cima-bridge-run1";
  ensureReproRuns(acq);
  let target = pipe ? reproRunId(pipe, acq) : null;
  if (!target || !allRuns.some((r) => r.id === target)) target = allRuns.find((r) => r.track === "repro")?.id;
  if (target) selectRun(target);
}
const reproAcqOpts = () => Object.entries(datasetsReg).filter(([, v]) => v.track === "repro")
  .map(([id, v]) => ({ id, label: v.label || id })).sort((a, b) => a.id.localeCompare(b.id));
const REPRO_SCANNERS = ["prisma", "cima"];
const REPRO_PROTOS = ["bridge", "local", "pulseq-online", "pulseq-offline"];
const REPRO_RUNS = ["run1", "run2", "run3"];
const acqExists = (id) => reproAcqOpts().some((a) => a.id === id);

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
  // χ-separation produces TWO source maps, so `produces` is an array; runLine writes them to a
  // directory and scores against a ground-truth directory.
  "chi-separation": { consumes: ["localfield", "r2prime", "chimap", "magnitude", "mask", "params"],
    produces: ["chi-para", "chi-dia"] },
  // R2′ estimation: multi-echo GRE magnitude in, R2′ (Hz) out (the GRE-only condition's generators).
  "r2prime-generation": { consumes: ["magnitude", "mask", "params"], produces: "r2prime" },
  // Brain extraction: magnitude in, binary mask out (the Harmonization dataset's masking step).
  "brain-extraction": { consumes: ["magnitude", "params"], produces: "mask" },
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
// slugs QSMxT can run is read from each algorithm's self-described `engine` (contains "QSM.rs"), with no
// per-method hardcoding, and the qsmxt flag follows from the stage.
const QSMXT_FLAG = {
  bfr: "--bf-algorithm", "unwrap+bfr": "--bf-algorithm",
  dipole: "--qsm-algorithm", "bfr+dipole": "--qsm-algorithm", "end-to-end": "--qsm-algorithm",
};
function renderHowToRun() {
  const el = $("how-to-run");
  if (!el) return;
  // Harmonization runs describe the same method chain as an in-silico composed pipeline, so the same
  // command generation applies: the section renders identically (bring your own NIfTIs; nothing to score).
  const bySlug = Object.fromEntries(algos.map((a) => [a.slug, a]));
  const stageOf = (s) => (bySlug[s] ? bySlug[s].stage : null);
  const isQsmRs = (slug) => { const a = bySlug[slug]; return !!(a && a.engine && a.engine.includes("QSM.rs")); };

  // ---- QSM-CI command (reproduces the scored artifact) ----
  const lines = [];
  // Harmonization (repro) reconstructions begin by making the brain mask with HD-BET, the masking
  // method that dataset uses. In-silico masks come from the phantom, so this step is repro-only.
  if (datasetOf(run) === "repro") lines.push(runLine("hd-bet-qsmci", "brain-extraction", false, ["magnitude"]));
  // One line per method step, in pipeline order; only the last is scored against a ground truth.
  // pipelineSteps() covers every shape: the matrix combo, a 2-part field-mapping + span pipeline
  // (whose span lives in run.slug, or, on the harmonization track, only in pipelineId), and a
  // single isolated method.
  // ...and the last step is scored against a ground truth — except on the harmonization track, which
  // is in-vivo data with none, so no --truth flag exists to offer there.
  const scored = datasetOf(run) !== "repro";
  const steps = pipelineSteps(run).filter((s) => bySlug[s] && stageOf(s));
  steps.forEach((s, i) => lines.push(runLine(s, stageOf(s), scored && i === steps.length - 1, bySlug[s].inputs)));
  if (!lines.length) { el.classList.add("hidden"); return; }
  const ciCmd = "pip install qsm-ci\n" + lines.join("\n");
  const chained = lines.length > 1;

  // ---- QSMxT command (only when every method step is QSM.rs-backed) ----
  const xtCmd = (() => {
    if (!steps.length || !steps.every(isQsmRs)) return null;   // every step must run on the QSM.rs engine
    const parts = ["qsmxt run /path/to/bids /path/to/output"];
    for (const s of steps) {
      const st = stageOf(s);
      // Field mapping is the one stage QSMxT names by unwrapping algorithm, not by method slug.
      if (st === "field-mapping") parts.push(`--unwrapping-algorithm ${s.replace(/-fieldmap$/, "")}`);
      else if (QSMXT_FLAG[st]) parts.push(`${QSMXT_FLAG[st]} ${s}`);
      else return null;   // a stage QSMxT has no flag for → no equivalent command
    }
    return parts.join(" \\\n  ");
  })();

  el.classList.remove("hidden");  // the div ships with Tailwind `hidden`; clear the class, not just inline style

  const codePane = (cmd, key, hidden) =>
    `<div data-pane="${key}" class="relative mt-3 ${hidden ? "hidden" : ""}">
      <button data-copy="${key}" class="absolute right-2 top-2 rounded-md bg-gray-800/80 px-2 py-1 text-xs font-medium text-gray-100 hover:bg-gray-700">Copy</button>
      <pre class="overflow-x-auto rounded-xl bg-gray-900 p-4 text-xs leading-relaxed text-gray-100"><code class="language-bash">${escapeHtml(cmd)}</code></pre>
    </div>`;
  const tabBtn = (key, label, active) =>
    `<button data-tab="${key}" class="rounded-md px-3 py-1 transition ${active ? "bg-white shadow-sm text-gray-900 dark:bg-gray-700 dark:text-gray-100" : "text-gray-500 hover:text-gray-700 dark:text-gray-400"}">${label}</button>`;

  const ciDesc = `Reproduce ${scored ? "the scored artifact" : "this reconstruction"} with the <a href="running.html" class="text-emerald-600 hover:underline"><code>qsm-ci</code></a> CLI:
      bring your own NIfTIs${chained ? ", chained stage by stage," : ""} or make a phantom with <code>qsm-forward</code>.${scored ? " Drop <code>--truth</code> to run without scoring." : ""}`;
  const xtDesc = `Run this ${steps.length > 1 ? "pipeline" : "method"} end-to-end on your own BIDS data with
      <a href="https://qsmxt.github.io" class="text-emerald-600 hover:underline">QSMxT</a> (unwrapping, background removal and dipole
      inversion in one command), on the same <a href="https://github.com/astewartau/QSM.rs" class="text-emerald-600 hover:underline">QSM.rs</a> engine QSM-CI uses.`;

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

  if (window.hljs) el.querySelectorAll("pre code.language-bash").forEach((c) => window.hljs.highlightElement(c));
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

let allRuns = [], algos = [], registry = {}, datasetsReg = {};
let nv = null, run, baseUrl, filter = "", navMode = "stages", domain = "qsm";
let defaultDragMode = null, panOn = false;   // NiiVue drag mode: default (contrast) captured at init; Pan-toggle state
let chisepPhantom = null;    // χ-separation phantom preference, remembered as you browse algorithms
// Base map shown underneath, and the default the layer strip opens on: the QSM ("recon") this page
// is about. The others are recon | truth | magnitude | totalfield | localfield, each shown only on a
// track that has it (see layerAvailable). It persists across run switches when the new run has it.
let curBase = "recon";
let chisepComp = "para";     // χ-separation source shown: para (χ+) | dia (χ−)
let showError = false;       // whether the error map is overlaid on top of the base
// Preload model: every candidate map (recon/truth[/-dia] + error[/-dia]) is loaded ONCE into
// nv.volumes and kept resident for the run; switching just toggles opacity (instant) instead of
// re-fetching. activeBaseVol / activeErrVol point the windowing controls at the map currently shown.
let activeBaseVol = null, activeErrVol = null, residentRunId = null, preloadPromise = null;
let baseCtl = null, errorCtl = null;         // the two windowing controls (base + error overlay)
let runRegions = null;       // the CURRENT run's per-region stats { chi|para|dia: {labels, recon, truth} }, or null
let metricsTab = "metrics";  // Metrics card tab: metrics | regions | error
let regionComp = "para";     // χ-sep component shown in the region tables (para = χ+, dia = χ−)

const $ = (id) => document.getElementById(id);
function badge(text, cls) {
  return `<span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${cls}">${text}</span>`;
}

// ---- sidebar ----------------------------------------------------------------
const uniq = (arr) => [...new Set(arr)];
// Composed pipelines for the OPEN dataset. Scoping by datasetOf keeps the in-silico matrix and the
// harmonization matrix (synthetic repro runs, see ensureReproRuns) as separate pools that the same
// pipelinesHTML renders identically; the two Pipelines sidebars are one code path.
const composedRuns = () => allRuns.filter((r) => r.mode === "composed" && r.combo && datasetOf(r) === domain);
// χ-separation methods (a distinct domain): one flat list, default variant only.
const chisepRuns = () => allRuns.filter((r) => (r.domain === "chisep" || r.stage === "chi-separation")
  && (r.variant || "default") === "default");
const hasChisep = () => chisepRuns().length > 0;
// χ-separation phantoms (the chisep-track entries of the dataset registry, shipped in
// algorithms.json's `datasets` block): a run row's `phantom` field names the phantom it was scored
// on; absence (older rows) means the track's default phantom.
const chisepPhantomIds = () => Object.keys(datasetsReg).filter((k) => datasetsReg[k].track === "chisep");
const chisepDefaultPhantom = () => chisepPhantomIds().find((k) => datasetsReg[k].default) || "chisep";
const chisepPhantomOf = (r) => (chisepPhantomIds().includes(r.phantom) ? r.phantom : chisepDefaultPhantom());
const phantomLabel = (p) => (datasetsReg[p] || {}).label || p;
// The χ-separation run for a method (`slug`) on a preferred phantom: fall back to the default
// phantom, then to whatever run exists. Drives both the deduped sidebar list and the phantom switch.
const chisepRunFor = (slug, phantom) => {
  const rs = chisepRuns().filter((r) => r.slug === slug);
  return rs.find((r) => chisepPhantomOf(r) === phantom)
    || rs.find((r) => chisepPhantomOf(r) === chisepDefaultPhantom())
    || rs[0];
};
// The phantoms a given method was scored on (default phantom first); the switch appears only for ≥2.
function chisepPhantomPeers() {
  if (!run || datasetOf(run) !== "chisep") return [];
  const d = chisepDefaultPhantom();
  return uniq(chisepRuns().filter((r) => r.slug === run.slug).map(chisepPhantomOf))
    .sort((a, b) => (a === d ? -1 : b === d ? 1 : a < b ? -1 : 1));
}
// In-vivo (2016 challenge) runs: a distinct DATASET (not just a domain), dipole-only, scored vs
// COSMOS + STI χ33. One flat list, default variant only, like χ-separation.
const isInvivo = (r) => r.track === "invivo";
const invivoRuns = () => allRuns.filter((r) => isInvivo(r) && (r.variant || "default") === "default");
const hasInvivo = () => invivoRuns().length > 0;
// Which dataset/domain sidebar view a run belongs to.
const datasetOf = (r) => r?.track === "repro" ? "repro"
  : isInvivo(r) ? "invivo"
  : (r.domain === "chisep" || r.stage === "chi-separation") ? "chisep" : "qsm";
const DATASET_LABEL = { invivo: "In vivo (2016)", qsm: "In silico (2019)", chisep: "χ-sep (2026)", repro: "Harmonization (2026)" };
// The scored phantom a run belongs to, normalising a missing `phantom` to the track default. Metric
// ranks pool only same-phantom runs: r2prime-generation and χ-separation methods each have one run per
// phantom, so without this the denominator counts the same method once per phantom (e.g. #x / 12 across
// six phantoms instead of #x / 2 among the two methods scored on this one).
const phantomKey = (r) => datasetOf(r) === "chisep" ? chisepPhantomOf(r) : (r?.phantom || "_default");

// The isolated-dipole run for `slug` on a given dataset: the "same algorithm, other dataset" target.
// Only dipole methods span the 2016/2019 datasets (in-vivo scores dipole only).
function dipoleRunOn(slug, dom) {
  if (dom === "invivo") return invivoRuns().find((r) => r.slug === slug);
  return allRuns.find((r) => r.slug === slug && !isInvivo(r) && datasetOf(r) === dom
    && r.mode === "isolated" && r.stage === "dipole" && (r.variant || "default") === "default");
}
// The datasets (2016 / 2019) on which the CURRENT method has an isolated dipole run, in display order.
function datasetPeers() {
  if (!run || run.stage !== "dipole" || run.mode !== "isolated") return [];
  return ["invivo", "qsm"].map((d) => ({ dom: d, run: dipoleRunOn(run.slug, d) })).filter((p) => p.run);
}
// The sidebar's dataset tabs BROWSE: they re-point the run list and nothing else. What's open in the
// content stays open — moving the current method/pipeline to another dataset is the job of the toggle
// above the viewer (switchDataset), which is a deliberate act on one run, not a change of listing.
// Harmonization is the only dataset whose runs are synthesized rather than loaded, so its pool has to
// be generated before its list can render.
async function browseDataset(dom) {
  if (dom === "repro") {
    await ensureReproJson();
    ensureReproRuns(acqExists(reproAcq) ? reproAcq : "cima-bridge-run1");
  }
  domain = dom;
  buildSidebar();
}
// Switch dataset while keeping the same algorithm open when it exists on the target (re-selecting its
// run there); otherwise just browse the target dataset's list.
function switchDataset(dom) {
  // The in-vivo (2016) challenge scored ONE stage — dipole inversion, isolated runs only — so Stages
  // is the only sidebar view that can show it (the Stages/Pipelines toggle is hidden while it's open).
  // Set the subtab on the way in, so toggling back to In silico (2019) lands on the stage list holding
  // the method you were looking at, not on the pipeline matrix it isn't in.
  if (dom === "invivo") navMode = "stages";
  // Harmonization: enter it in-place. Keep the same pipeline open when the current run is a composed
  // one; from an isolated run there's no analog, so enterRepro(null) opens the first harmonization
  // pipeline instead.
  if (dom === "repro") {
    const pipe = reproMode ? reproPipe : pipelineIdOf(run);
    enterRepro(pipe, reproAcq);
    return;
  }
  // Leaving harmonization for any scored dataset. Prefer the SAME pipeline's in-silico composed run
  // (keep the method open); otherwise open the target dataset's first run so the tab just browses it.
  // selectRun re-derives domain and clears reproMode, so this fully transitions out of harmonization.
  if (reproMode) {
    if (dom === "qsm") {
      const simId = simRunIdOf(reproPipe);
      if (allRuns.some((r) => r.id === simId)) { selectRun(simId); return; }
    }
    const first = dom === "invivo" ? invivoRuns()[0]
      : dom === "chisep" ? chisepRuns()[0]
      : allRuns.find((r) => !isInvivo(r) && datasetOf(r) === dom);
    if (first) selectRun(first.id);
    return;
  }
  const peer = run ? dipoleRunOn(run.slug, dom) : null;
  if (peer) { selectRun(peer.id); return; }  // selectRun re-derives `domain` from the chosen run
  domain = dom;
  buildSidebar();
}
// Span methods (bfr+dipole / end-to-end, e.g. NeXtQSM/TGV/QSMART/iQSM) go straight to a χ map in one
// step, so they have no bfr/dipole pair for the matrix axes. Every run of one, in any field-mapping
// context: the isolated run, the ground-truth-field composed run, and one per field-mapping method.
// (unwrap+bfr methods produce localfield, not χ, so they sit on the matrix's background-removal axis
// instead and are excluded here.) Their OWN stage comes from the manifest, since a composed run is
// stamped with the pipeline's stage ("field-mapping+bfr+dipole"), not the span's.
const SPAN_STAGES = ["bfr+dipole", "end-to-end"];
const spanRuns = () => allRuns.filter((r) => datasetOf(r) === domain
  && (r.variant || "default") === "default"       // tuned variants are reached via the toggle
  && !r.combo?.bfr && !r.combo?.dipole            // a full combo belongs on the axes
  && SPAN_STAGES.includes(algoStage(r.slug)));
// One row per METHOD in each span group (not one per combination): the list stays put while the
// field-mapping axis changes underneath it, exactly like the bfr and dipole axes.
const spanSlugs = (stage) => uniq(spanRuns().filter((r) => algoStage(r.slug) === stage).map((r) => r.slug));
// The field-mapping method a run was paired with ("gt" = none/ground truth), read from its steps so
// it works for a matrix combo, a 2-part in-silico pipeline and a harmonization row alike.
const fmapOf = (r) => { const st = pipelineSteps(r); return st.length > 1 && algoStage(st[0]) === "field-mapping" ? st[0] : "gt"; };
// A bfr+dipole span still consumes a field map, so it pairs with the field-mapping axis: resolve the
// row against the CURRENT field mapping (undefined → the axis renders it greyed, as for any pairing
// that wasn't run). End-to-end methods take raw phase, so they have no field-mapping choice at all.
const findSpan = (fmap, slug) => spanRuns().find((r) => r.slug === slug && r.mode === "composed" && fmapOf(r) === fmap);
const findEndToEnd = (slug) => spanRuns().find((r) => r.slug === slug && r.mode === "composed")
  || spanRuns().find((r) => r.slug === slug);
const fmapsList = () => {
  const s = uniq(composedRuns().map((r) => r.combo.field_mapping || "gt"));
  return s.includes("gt") ? ["gt", ...s.filter((x) => x !== "gt")] : s;
};
// Single-step spans (bfr+dipole / end-to-end, e.g. TGV/MEDI/AutoQSM) have a composed run with no
// bfr/dipole in the combo, so filter those out so they don't add an empty "Undefined" row to the axes.
const bfrList = () => uniq(composedRuns().map((r) => r.combo.bfr).filter(Boolean));
const dipoleList = () => uniq(composedRuns().map((r) => r.combo.dipole).filter(Boolean));
const findPipeline = (f, b, d) => composedRuns().find((r) =>
  (r.combo.field_mapping || "gt") === f && r.combo.bfr === b && r.combo.dipole === d);
const algoName = (slug) => { const a = algos.find((x) => x.slug === slug); return (a && a.name) || slug; };
const algoStage = (slug) => { const a = algos.find((x) => x.slug === slug); return a && a.stage; };
// A method still shipped by QSM-CI: present in the manifest and not hidden. Mirrors loadRuns()'s
// hidden-slug filter, which drops the same methods from the in-silico runs.
const liveAlgo = (slug) => { const a = algos.find((x) => x.slug === slug); return !!a && !a.hidden; };
// The ordered method slugs a run is made of. A matrix combo names its stages explicitly; a 2-part
// pipeline (field mapping + a bfr+dipole/end-to-end span) keeps the span in `slug`, and on the
// harmonization track carries no combo at all — there the whole pipeline lives in `pipelineId`.
// Anything else is a single method. Drops "gt" (no field-mapping step) and repeats.
const pipelineSteps = (r) => {
  if (!r) return [];
  const c = r.combo;
  const raw = c ? [c.field_mapping, c.bfr, c.dipole, (!c.bfr && !c.dipole) ? r.slug : null]
    : r.pipelineId ? r.pipelineId.split("+") : [r.slug];
  return raw.filter((x, i, a) => x && x !== "gt" && a.indexOf(x) === i);
};
// The "a+b+c" pipeline id of a composed run, the key both repro.json and the in-silico run ids use.
// Derived from the steps rather than `slug`, which holds only the span for a 2-part pipeline.
const pipelineIdOf = (r) => r?.pipelineId || (r?.mode === "composed" ? pipelineSteps(r).join("+") : null);
const fmapName = (m) => (m === "gt" ? "Ground truth" : algoName(m));
// Every sidebar list is ordered the same way — alphabetically by the name shown, ignoring case and
// accents, digits compared as numbers — so switching tab, dataset or stage never reshuffles it.
const NAME_COLLATOR = new Intl.Collator(undefined, { sensitivity: "base", numeric: true });
const byName = (nameOf) => (a, b) => NAME_COLLATOR.compare(nameOf(a), nameOf(b));

function currentCombo() {
  // Only a run from the dataset being listed says anything about ITS axes. While browsing another one
  // (the tabs don't change what's open) fall back to that dataset's defaults, rather than resolving
  // every row against a combo it has no runs for — e.g. a ground-truth field mapping, which the
  // harmonization track has none of, would grey out its whole matrix.
  const cur = datasetOf(run) === domain ? run : null;
  // A bfr+dipole span stands in for BOTH the bfr and dipole axes, so what it selects is a field
  // mapping + itself: report the pairing it was opened with (`span`) and the bfr/dipole axes fall
  // back to their defaults, so clicking one of those is what leaves the span behind.
  if (cur?.mode === "composed" && !cur.combo?.bfr && !cur.combo?.dipole && algoStage(cur.slug) === "bfr+dipole")
    return { fmap: fmapOf(cur), bfr: bfrList()[0], dipole: dipoleList()[0], span: cur.slug };
  if (cur?.combo) return { fmap: cur.combo.field_mapping || "gt", bfr: cur.combo.bfr, dipole: cur.combo.dipole };
  const c = { fmap: fmapsList()[0], bfr: bfrList()[0], dipole: dipoleList()[0] };
  if (cur?.mode === "isolated") { if (cur.stage === "dipole") c.dipole = cur.slug; if (cur.stage === "bfr") c.bfr = cur.slug; }
  return c;
}
function runItem(r, activeId) {
  const active = r && r.id === activeId;
  // χ-separation rows carry no plain xsim; headline the mean χ+/χ− per-ROI MSPE (the leaderboard's
  // ranking metric, following Ridani et al. 2026), falling back to detrended NRMSE where MSPE is absent.
  const m = (r && r.metrics) || {};
  // Harmonization rows headline the inter-scanner |a−1| (reproducibility, lower better) as a %.
  if (r && r.track === "repro") {
    const label = m.repro_inter != null ? (100 * m.repro_inter).toFixed(1) + "%" : "—";
    const active = r.id === activeId;
    return `<button data-id="${r.id}"
      class="run-item w-full text-left rounded-lg px-2.5 py-1.5 text-sm flex items-center justify-between gap-2 transition
        ${active ? "bg-indigo-50 text-indigo-700 font-medium dark:bg-indigo-500/15 dark:text-indigo-300" : "text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800"}">
      <span class="truncate">%NAME%</span>
      <span class="shrink-0 tabular-nums text-xs ${active ? "text-indigo-500" : "text-gray-400"}" title="inter-scanner |a−1|">${label}</span>
    </button>`;
  }
  let hv, hk = "xsim";
  // R2′ generators headline their detrended NRMSE (the champion-selection metric on the GRE-only
  // board) rather than xSIM (which is a secondary agreement number for a relaxation map).
  if (r && r.stage === "r2prime-generation" && m.nrmse_detrend != null) { hv = m.nrmse_detrend; hk = "nrmse_detrend"; }
  else if (m.xsim != null) hv = m.xsim;
  else if (m.para_mspe != null && m.dia_mspe != null) { hv = (m.para_mspe + m.dia_mspe) / 2; hk = "mspe"; }
  else if (m.para_nrmse_detrend != null && m.dia_nrmse_detrend != null) { hv = (m.para_nrmse_detrend + m.dia_nrmse_detrend) / 2; hk = "nrmse_detrend"; }
  else if (m.para_xsim != null && m.dia_xsim != null) hv = (m.para_xsim + m.dia_xsim) / 2;
  else hv = r ? val(r, "xsim") : null;
  const label = r ? (r.status === "DNF" ? "DNF" : fmt(hv, hk)) : "—";
  const dis = !r || r.status === "DNF";
  return `<button data-id="${r ? r.id : ""}"
    class="run-item w-full text-left rounded-lg px-2.5 py-1.5 text-sm flex items-center justify-between gap-2 transition
      ${active ? "bg-indigo-50 text-indigo-700 font-medium dark:bg-indigo-500/15 dark:text-indigo-300" : "text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800"} ${!r ? "opacity-40 cursor-default" : ""}">
    <span class="truncate">%NAME%</span>
    <span class="shrink-0 tabular-nums text-xs ${dis ? "text-gray-300 dark:text-gray-600" : active ? "text-indigo-500" : "text-gray-400"}">${label}</span>
  </button>`;
}
// Which sidebar groups are collapsed, by key. Module-level so the state survives buildSidebar(),
// which rebuilds the whole list on every selection.
const collapsedGroups = new Set();
// One sidebar group: a header that toggles its rows. `rows` is the already-rendered run items; an
// empty group renders nothing, exactly as before.
function groupHTML(key, label, rows) {
  if (!rows) return "";
  // A collapsed group opens while a filter is active — otherwise typing a method name that lives in
  // one would look like the search found nothing. Clearing the filter restores the collapsed state.
  const off = !filter && collapsedGroups.has(key);
  // The chevron's size and rotation are inline: styles.css is a pre-built purge, so utilities it
  // doesn't already contain (w-3, -rotate-90) would silently do nothing.
  return `<div class="mb-3"><button data-group="${key}" class="group-toggle flex w-full items-center px-2.5 pt-1 pb-1 text-left text-[11px] font-semibold uppercase tracking-wide text-gray-400 transition hover:text-gray-600 dark:hover:text-gray-300">
      <svg viewBox="0 0 20 20" fill="currentColor" style="width:9px;height:9px;flex:none;margin-right:.4rem;transition:transform .15s ease;transform:rotate(${off ? "-90deg" : "0deg"})"><path d="M4 6.5h12L10 14z"/></svg>
      <span>${label}</span></button><div${off ? " hidden" : ""}>${rows}</div></div>`;
}
function stagesHTML() {
  const f = filter.toLowerCase();
  // Pipeline order: field mapping → background removal → dipole inversion, then the combined
  // single-method spans (bfr+dipole like TGV/QSMART/MEDI, unwrap+bfr like HARPERELLA, end-to-end).
  return ["field-mapping", "bfr", "dipole", "bfr+dipole", "unwrap+bfr", "end-to-end"].map((s) => {
    const rs = allRuns.filter((r) => r.mode === "isolated" && r.stage === s && (r.variant || "default") === "default" && !isInvivo(r) && (!f || r.name.toLowerCase().includes(f)))
      .sort(byName((r) => r.name));
    return groupHTML("stage:" + s, STAGE_LABEL[s] || s, rs.map((r) => runItem(r, run?.id).replace("%NAME%", r.name)).join(""));
  }).join("") || `<p class="p-3 text-sm text-gray-400">No matches.</p>`;
}
function pipelinesHTML() {
  const cur = currentCombo();
  const f = filter.toLowerCase();
  const axis = (title, methods, kind) => {   // key by axis, not title, so the collapsed state is stable
    const label = (m) => (kind === "fmap" ? fmapName(m) : algoName(m));
    const rows = methods.filter((m) => !f || label(m).toLowerCase().includes(f)).sort(byName(label)).map((m) => {
      // With a bfr+dipole span selected, the field-mapping axis re-pairs THAT span (ROMEO → QSMART,
      // Laplacian → QSMART); otherwise it swaps the field mapping of the bfr×dipole combo.
      const rn = kind === "fmap" ? (cur.span ? findSpan(m, cur.span) : findPipeline(m, cur.bfr, cur.dipole))
        : kind === "bfr" ? findPipeline(cur.fmap, m, cur.dipole) : findPipeline(cur.fmap, cur.bfr, m);
      return runItem(rn, run?.id).replace("%NAME%", label(m));
    }).join("");
    return groupHTML("axis:" + kind, title, rows);
  };
  const matrix = composedRuns().length
    ? axis("Field mapping", fmapsList(), "fmap") + axis("Background removal", bfrList(), "bfr") + axis("Dipole inversion", dipoleList(), "dipole")
    : "";
  // Single-step χ producers, grouped by their self-described stage (not hardcoded per method): the
  // same split as the Stages view and the leaderboard: bfr+dipole and end-to-end are distinct spans.
  // Each is a group of METHODS, like the axes above — a bfr+dipole method resolves against the
  // current field mapping (so picking one leaves the field-mapping axis in charge of the other half),
  // an end-to-end method takes raw phase and has no field mapping to pick.
  const spanGroup = (stage) => {
    const slugs = spanSlugs(stage).filter((m) => !f || algoName(m).toLowerCase().includes(f)).sort(byName(algoName));
    return groupHTML("span:" + stage, STAGE_LABEL[stage] || stage,
      slugs.map((m) => runItem(stage === "bfr+dipole" ? findSpan(cur.fmap, m) : findEndToEnd(m), run?.id).replace("%NAME%", algoName(m))).join(""));
  };
  const combinedSection = spanGroup("bfr+dipole") + spanGroup("end-to-end");
  return (matrix + combinedSection) ||
    `<p class="p-3 text-sm text-gray-400">No pipeline combinations available yet; the composed matrix is computed by the nightly job.</p>`;
}
function chisepHTML() {
  const f = filter.toLowerCase();
  const rs = chisepRuns().filter((r) => !f || r.name.toLowerCase().includes(f));
  if (!rs.length) return `<p class="p-3 text-sm text-gray-400">No χ-separation methods yet.</p>`;
  // ONE list of methods (deduped by algorithm), regardless of how many phantoms each was scored on.
  // Each row points at the method's run on the currently-selected phantom (`chisepPhantom`, remembered
  // as you browse); the phantom selector above the viewer swaps phantom in place. So the row's headline
  // metric and the volume it opens both track the chosen phantom.
  const group = (key, label, pool) => groupHTML(key, label,
    uniq(pool.map((r) => r.slug)).map((slug) => chisepRunFor(slug, chisepPhantom))
      .sort(byName((r) => r.name))
      .map((r) => runItem(r, run?.id).replace("%NAME%", r.name)).join(""));
  // R2′ generators live on the same phantoms but are their own category: they estimate an input
  // (R2′ from GRE magnitude), they don't separate sources.
  return group("chisep:sep", "χ-separation", rs.filter((r) => r.stage !== "r2prime-generation"))
       + group("chisep:r2p", "R2′ estimation", rs.filter((r) => r.stage === "r2prime-generation"));
}
function invivoHTML() {
  const f = filter.toLowerCase();
  const rs = invivoRuns().filter((r) => !f || r.name.toLowerCase().includes(f)).sort(byName((r) => r.name));
  if (!rs.length) return `<p class="p-3 text-sm text-gray-400">No in-vivo runs yet.</p>`;
  return groupHTML("invivo:dipole", STAGE_LABEL.dipole,
    rs.map((r) => runItem(r, run?.id).replace("%NAME%", r.name)).join(""));
}
// Mark the tab the open page comes from. The mark IS the amber label colour applied in buildSidebar —
// nothing is added to the tab, so no label can be pushed onto a second line; this only carries the
// explanation. Reached only when that tab isn't the one being browsed: when it is, it's the selected
// tab and there's nothing to disambiguate.
function markHome(btn, on) {
  if (on) btn.title = "The page you're viewing comes from here";
  else btn.removeAttribute("title");
}
function buildSidebar() {
  // Fall back to the in-silico dataset if the selected one has no runs (not in repro mode, which is
  // its own dataset).
  if (!reproMode) {
    if (domain === "chisep" && !hasChisep()) domain = "qsm";
    if (domain === "invivo" && !hasInvivo()) domain = "qsm";
  }
  // Dataset toggle: one button per dataset. In silico is always shown; χ-sep / In-vivo / Harm. 2026
  // appear whenever that dataset has any runs (harmonization = repro.json has pipelines), so the tab is
  // always available to browse, not gated on the currently-open run.
  // Where the OPEN page lives, which the tabs no longer follow: an amber dot marks the dataset (and
  // the Stages/Pipelines view) the run on screen belongs to, so a sidebar listing something else is
  // never mistaken for what's rendered. When you're browsing its own dataset the dot simply sits on
  // the selected tab.
  const homeDom = run ? datasetOf(run) : null;
  const homeMode = run ? (run.mode === "composed" ? "pipelines" : "stages") : null;
  document.querySelectorAll("#domain-toggle button").forEach((b) => {
    const hide = (b.dataset.domain === "chisep" && !hasChisep())
      || (b.dataset.domain === "invivo" && !hasInvivo())
      || (b.dataset.domain === "repro" && !hasRepro());
    const home = b.dataset.domain === homeDom;
    b.className = "flex-1 rounded-md px-2 py-1 transition " + (hide ? "hidden " : "")
      + (b.dataset.domain === domain ? "bg-white shadow-sm text-gray-900 dark:bg-gray-700 dark:text-gray-100"
        : home ? "text-amber-600 hover:text-amber-700 dark:text-amber-400"
        : "text-gray-500 hover:text-gray-700 dark:text-gray-400");
    markHome(b, home);
  });
  $("domain-toggle")?.classList.remove("hidden");

  $("run-filter")?.classList.remove("hidden");
  // Harmonization is composed-only, so it's always the Pipelines matrix (no Stages split). The
  // χ-separation / in-vivo lists are flat too. Everything else keeps the Stages/Pipelines toggle.
  // `mode` is the view this dataset can show; `navMode` (the remembered choice) is left alone, so
  // browsing through harmonization and back doesn't silently move you off the Stages list.
  const mode = domain === "repro" ? "pipelines" : navMode;
  const flat = domain === "chisep" || domain === "invivo" || domain === "repro";
  $("nav-toggle")?.classList.toggle("hidden", flat);
  document.querySelectorAll("#nav-toggle button").forEach((b) => {
    // The view that lists the open run: a composed pipeline lives in Pipelines, an isolated method in
    // Stages. Only meaningful for the run's own dataset — marking Pipelines while you browse another
    // dataset's list would point at a row that isn't there.
    const home = domain === homeDom && b.dataset.mode === homeMode;
    b.className = "flex-1 rounded-md px-2 py-1 transition " +
      (b.dataset.mode === mode ? "bg-white shadow-sm text-gray-900 dark:bg-gray-700 dark:text-gray-100"
        : home ? "text-amber-600 hover:text-amber-700 dark:text-amber-400"
        : "text-gray-500 hover:text-gray-700 dark:text-gray-400");
    markHome(b, home);
  });
  $("run-list").innerHTML = domain === "chisep" ? chisepHTML()
    : domain === "invivo" ? invivoHTML()
    : (mode === "stages" ? stagesHTML() : pipelinesHTML());
  $("run-list").querySelectorAll(".run-item").forEach((b) => b.addEventListener("click", () => { if (b.dataset.id) selectRun(b.dataset.id); }));
  // Collapse/expand a group in place (no re-render), remembering the state for the next buildSidebar.
  $("run-list").querySelectorAll(".group-toggle").forEach((b) => b.addEventListener("click", () => {
    const off = !collapsedGroups.has(b.dataset.group);
    collapsedGroups[off ? "add" : "delete"](b.dataset.group);
    b.nextElementSibling.hidden = off;
    b.querySelector("svg").style.transform = `rotate(${off ? "-90deg" : "0deg"})`;
    fitSidebar();
  }));
  fitSidebar();
}
// Keep the sidebar inside the window: the run list gets whatever room is left below its own top edge
// and scrolls internally. Measured rather than a fixed max-height, because that top moves — the aside
// is sticky (it rises to the sticky offset as the page scrolls) and the header above the list changes
// height between datasets (the Stages/Pipelines toggle is hidden on the flat ones).
let fitLast = "";
function fitSidebar() {
  const nav = $("run-list");
  if (!nav) return;
  const h = Math.max(160, window.innerHeight - nav.getBoundingClientRect().top - 16) + "px";
  if (h !== fitLast) { fitLast = h; nav.style.maxHeight = h; }   // only touch style when it changes
}
addEventListener("resize", fitSidebar);
addEventListener("scroll", fitSidebar, { passive: true });   // the sticky aside rises as you scroll
// In-content dataset switch for a COMPOSED pipeline, shown above the viewer/metrics: toggle the SAME
// pipeline between its in-silico (2019) score and its harmonization (2026) reproducibility view, and,
// in harmonization view, pick the scanner/protocol/run acquisition. Both directions switch IN-PLACE
// via selectRun (no page navigation), and the toggle renders on BOTH sides so you can go back. Rendered
// into the same #dataset-switch slot the dipole 2016⇄2019 toggle uses.
function renderPipelineDatasetSwitch() {
  const el = $("dataset-switch");
  if (!el) return;
  const inRepro = reproMode;
  const pipe = inRepro ? reproPipe : pipelineIdOf(run);
  const simId = simRunIdOf(pipe);
  const hasSim = allRuns.some((r) => r.id === simId);
  const hasRepro = pipeHasRepro(pipe);
  const acq = acqExists(reproAcq) ? reproAcq : "cima-bridge-run1";
  const parts = acq.split("-");
  const scanner = parts[0], runNo = parts[parts.length - 1], proto = parts.slice(1, -1).join("-");
  const tbtn = (key, label, active, enabled, tip) =>
    `<button data-ds="${key}" ${enabled ? "" : `disabled title="${tip}"`} class="rounded-md px-3 py-1.5 transition ${active
      ? "bg-white shadow-sm text-gray-900 dark:bg-gray-700 dark:text-gray-100"
      : enabled ? "text-gray-500 hover:text-gray-700 dark:text-gray-400"
                : "text-gray-300 dark:text-gray-600 cursor-not-allowed"}">${label}</button>`;
  const sel = (id, opts, cur) =>
    `<select data-repro="${id}" class="rounded-lg border-gray-300 text-xs py-1 dark:bg-gray-800 dark:border-gray-700">`
    + opts.map((o) => `<option value="${o.v}" ${o.v === cur ? "selected" : ""}>${o.l}</option>`).join("") + `</select>`;
  // Acquisition pickers only make sense in the harmonization view; the in-silico side has one dataset.
  const pickers = inRepro ? `<div class="ml-auto flex items-center gap-2">
      ${sel("scanner", REPRO_SCANNERS.map((s) => ({ v: s, l: s === "cima" ? "Cima.X" : "Prisma" })), scanner)}
      ${sel("proto", REPRO_PROTOS.map((p) => ({ v: p, l: p.replace("pulseq-online", "Pulseq online").replace("pulseq-offline", "Pulseq offline") })), proto)}
      ${sel("run", REPRO_RUNS.map((r) => ({ v: r, l: r })), runNo)}
    </div>` : "";
  el.innerHTML = `<div class="flex flex-wrap items-center gap-3">
    <div class="inline-flex rounded-lg bg-gray-100 p-1 text-xs font-medium dark:bg-gray-800">
      ${tbtn("qsm", "In silico (2019)", !inRepro, hasSim, "this pipeline has no in-silico run")}
      ${tbtn("repro", "Harmonization (2026)", inRepro, hasRepro, "this pipeline has no harmonization result")}
    </div>
    ${pickers}
  </div>`;
  el.querySelectorAll("[data-ds]").forEach((b) => b.addEventListener("click", () => {
    const key = b.dataset.ds;
    if (key === "qsm" && inRepro && hasSim) selectRun(simId);
    else if (key === "repro" && !inRepro && hasRepro) enterRepro(pipe, reproAcq);
  }));
  el.querySelectorAll("[data-repro]").forEach((s) => s.addEventListener("change", () => {
    const g = (k) => el.querySelector(`[data-repro="${k}"]`).value;
    const a = `${g("scanner")}-${g("proto")}-${g("run")}`;
    ensureReproRuns(a);                       // regenerate the pool for the new acquisition
    selectRun(reproRunId(pipe, a));           // reopen the same pipeline there
  }));
  el.classList.remove("hidden");
}

// Reproducibility stats for the open pipeline (from repro.json) in place of the accuracy metrics.
// Rank this pipeline's reproducibility value for `field` among ALL harmonization pipelines (lower
// |a−1| is better). Same {rank, n, t} shape as metricRank so the rank cell renders identically.
function reproRank(field) {
  const v = reproJson?.pipelines?.[reproPipe]?.[field];
  if (v == null) return null;
  const vals = Object.values(reproJson.pipelines || {}).map((n) => n[field]).filter((x) => x != null);
  if (vals.length < 2) return null;
  const rank = 1 + vals.filter((x) => x < v).length;
  const [lo, hi] = robustRange(vals);
  let t = hi === lo ? 0.5 : (v - lo) / (hi - lo);
  return { rank, n: vals.length, t: 1 - t };   // lower value = higher goodness
}
function renderReproStats() {
  const node = reproJson?.pipelines?.[reproPipe];
  const hasRegions = !!(runRegions && runRegions.chi && runRegions.chi.recon);
  // Reuse the metrics tab strip as Reproducibility | Regions (the repro track has no ground truth, so no
  // Error tab). The per-region χ means come from the Hub regions.json (loadRunRegions → runRegions).
  const tabs = $("metrics-tabs");
  if (tabs) {
    tabs.classList.toggle("hidden", !hasRegions);
    const mBtn = tabs.querySelector('[data-mtab="metrics"]'); if (mBtn) mBtn.textContent = "Reproducibility";
    tabs.querySelector('[data-mtab="error"]')?.classList.add("hidden");
    if (!hasRegions) metricsTab = "metrics";
    const tab = metricsTab === "regions" ? "regions" : "metrics";
    tabs.querySelectorAll("[data-mtab]").forEach((b) => {
      const on = b.dataset.mtab === tab;
      ["bg-white", "shadow-sm", "text-gray-900", "dark:bg-gray-700", "dark:text-gray-100"].forEach((c) => b.classList.toggle(c, on));
      ["text-gray-500", "dark:text-gray-400"].forEach((c) => b.classList.toggle(c, !on));
    });
    if (tab === "regions") {
      $("metrics-table-wrap")?.classList.add("hidden");
      $("metrics-regions-wrap")?.classList.remove("hidden");
      return renderReproRegionTable(runRegions.chi);
    }
  }
  $("metrics-regions-wrap")?.classList.add("hidden");
  $("metrics-sub").textContent = "Reproducibility of this pipeline across the harmonization acquisitions: orthogonal per-ROI ax+b fits, |a−1| (median).";
  const rankCell = (rk, label) => rk
    ? `<span class="inline-block rounded-md px-1.5 py-0.5 text-xs font-semibold text-white shadow-sm" style="background:${heatScale(rk.t)}" data-tip="Rank ${rk.rank} of ${rk.n} harmonization pipelines for ${label}">#${rk.rank}<span class="opacity-70"> / ${rk.n}</span></span>`
    : `<span class="text-gray-300 dark:text-gray-600">—</span>`;
  // A reproducibility |a−1| row: value as a %, ranked against every other pipeline.
  const row = (label, field, tip) => {
    const v = node ? node[field] : null;
    return `<tr class="border-t border-gray-100 dark:border-gray-800">`
      + `<td class="py-2 pr-3 text-gray-600 dark:text-gray-300"><span class="has-tip" data-tip="${tip}">${label}</span></td>`
      + `<td class="py-2 text-right tabular-nums font-medium text-gray-900 dark:text-gray-100">${v == null ? ", " : (100 * v).toFixed(1) + "%"}</td>`
      + `<td class="py-2 pl-3 text-right">${rankCell(reproRank(field), label)}</td></tr>`;
  };
  // A resource row (runtime / peak memory / avg CPU): value only, folded on from the run's Hub trace.
  const resRow = (label, v, fk, tip) => v == null ? "" :
    `<tr class="border-t border-gray-100 dark:border-gray-800"><td class="py-2 pr-3 text-gray-500 dark:text-gray-400"><span class="has-tip" data-tip="${tip}">${label}</span></td>`
    + `<td class="py-2 text-right tabular-nums font-medium text-gray-700 dark:text-gray-300">${fmt(v, fk)}</td><td></td></tr>`;
  let body = node
    ? row("Test–retest |a−1|", "test_retest_mean_abs_slope_dev", "Within-scanner run-to-run, median over pairs. Lower = more repeatable.")
      + row("Inter-scanner |a−1|", "inter_scanner_mean_abs_slope_dev", "Prisma↔Cima for matched protocol+run. The harmonization headline.")
      + row("vs bridge |a−1|", "inter_protocol_mean_abs_slope_dev", "Each protocol vs the bridge protocol, same scanner.")
    : `<tr><td class="py-3 text-gray-400" colspan="3">No reproducibility summary for this pipeline yet.</td></tr>`;
  const res = resRow("Runtime", run.runtime_s, "runtime_s", "Whole-pipeline wall-clock on this acquisition (from the CPU/RAM trace).")
    + resRow("Peak memory", run.mem_peak_bytes, "mem_peak_bytes", "Peak resident memory during the run.")
    + resRow("Avg CPU", run.cpu_cores_avg, "cpu_cores_avg", "Average CPU cores busy over the run.");
  if (res) body += `<tr><td colspan="3" class="pt-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">Resources · ${escapeHtml(phantomLabel(reproAcq) || reproAcq)}</td></tr>` + res;
  $("metrics-body").innerHTML = body;
  const wrap = $("metrics-table-wrap"); if (wrap) wrap.classList.remove("hidden");
}

// Per-region χ means for a harmonization run: recon-only (no ground truth), aseg-labelled, published to
// the Hub as regions.json. `block` is the run's `chi` block { labels:{id:name}, recon:{id:{n,mean,std,median}} }.
function renderReproRegionTable(block) {
  $("metrics-sub").textContent = "Susceptibility per segmented region on this acquisition (SynthSeg labels): mean ± SD within each ROI (ppm). No ground truth on the harmonization track.";
  const labels = block.labels || {}, recon = block.recon || {};
  const ids = Object.keys(recon).sort((a, b) => (labels[a] || a).localeCompare(labels[b] || b));
  if (!ids.length) {
    $("metrics-regions-wrap").innerHTML = `<p class="py-3 text-sm text-gray-400">No regional statistics for this run.</p>`;
    return;
  }
  const rows = ids.map((k) => {
    const r = recon[k];
    return `<tr class="border-t border-gray-100 dark:border-gray-800">`
      + `<td class="py-1.5 pr-3 text-gray-600 dark:text-gray-300">${escapeHtml(labels[k] || k)}</td>`
      + `<td class="py-1.5 text-right tabular-nums font-medium text-gray-900 dark:text-gray-100">${p3(r.mean)}</td>`
      + `<td class="py-1.5 pl-3 text-right tabular-nums text-gray-500 dark:text-gray-400">${p3(r.std)}</td>`
      + `<td class="py-1.5 pl-3 text-right tabular-nums text-gray-400 dark:text-gray-500">${r.n.toLocaleString()}</td></tr>`;
  }).join("");
  $("metrics-regions-wrap").innerHTML = `<table class="w-full text-sm"><thead><tr class="text-left text-[11px] uppercase tracking-wide text-gray-400">`
    + `<th class="pb-2">Region</th><th class="pb-2 text-right">Mean</th><th class="pb-2 pl-3 text-right">SD</th><th class="pb-2 pl-3 text-right">Voxels</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function renderDatasetSwitch() {
  // A composed pipeline (in harmonization OR in-silico) toggles the same pipeline between its 2019
  // score and its 2026 reproducibility view, whenever it exists on the other side.
  if (reproMode || (run?.mode === "composed" && pipeHasRepro(pipelineIdOf(run)))) return renderPipelineDatasetSwitch();
  const el = $("dataset-switch");
  if (!el) return;
  const peers = datasetPeers();
  if (peers.length < 2) { el.classList.add("hidden"); el.innerHTML = ""; return; }
  const cur = datasetOf(run);
  const btns = peers.map((p) => {
    const on = p.dom === cur;
    return `<button data-switch="${p.dom}" class="rounded-md px-3 py-1.5 transition ${on
      ? "bg-white shadow-sm text-gray-900 dark:bg-gray-700 dark:text-gray-100"
      : "text-gray-500 hover:text-gray-700 dark:text-gray-400"}">${DATASET_LABEL[p.dom]}</button>`;
  }).join("");
  el.innerHTML = `<div class="flex flex-wrap items-center gap-3">
    <div class="inline-flex rounded-lg bg-gray-100 p-1 text-xs font-medium dark:bg-gray-800">${btns}</div>
  </div>`;
  el.querySelectorAll("[data-switch]").forEach((b) =>
    b.addEventListener("click", () => switchDataset(b.dataset.switch)));
  el.classList.remove("hidden");
}
// In-content phantom switch, shown above the viewer/metrics only for a χ-separation method scored on
// more than one phantom: swap the phantom, same method. Mirrors renderDatasetSwitch.
function renderChisepPhantomSwitch() {
  const el = $("chisep-phantom-switch");
  if (!el) return;
  const phs = chisepPhantomPeers();
  if (phs.length < 2) { el.classList.add("hidden"); el.innerHTML = ""; return; }
  const cur = chisepPhantomOf(run);
  const btns = phs.map((p) => {
    const on = p === cur;
    return `<button data-phantom="${p}" class="rounded-md px-3 py-1.5 transition ${on
      ? "bg-white shadow-sm text-gray-900 dark:bg-gray-700 dark:text-gray-100"
      : "text-gray-500 hover:text-gray-700 dark:text-gray-400"}">${phantomLabel(p)}</button>`;
  }).join("");
  el.innerHTML = `<div class="flex flex-wrap items-center gap-3">
    <div class="inline-flex rounded-lg bg-gray-100 p-1 text-xs font-medium dark:bg-gray-800">${btns}</div>
  </div>`;
  el.querySelectorAll("[data-phantom]").forEach((b) =>
    b.addEventListener("click", () => switchChisepPhantom(b.dataset.phantom)));
  el.classList.remove("hidden");
}
// Swap the phantom while keeping the same χ-separation method open (re-selecting its run there).
function switchChisepPhantom(p) {
  chisepPhantom = p;
  const target = run ? chisepRunFor(run.slug, p) : null;
  if (target) selectRun(target.id);
}
function selectRun(id) {
  run = allRuns.find((r) => r.id === id);
  if (!run) return;
  domain = datasetOf(run);   // keep the sidebar on the dataset this run belongs to
  reproMode = domain === "repro";
  if (reproMode) {
    reproPipe = run.pipelineId; reproAcq = run.phantom;   // deep-link by pipeline + acquisition
    history.replaceState(null, "", `?pipeline=${encodeURIComponent(reproPipe)}&dataset=repro&acq=${reproAcq}`);
  } else {
    if (domain === "chisep") chisepPhantom = chisepPhantomOf(run);   // remember the phantom being viewed
    history.replaceState(null, "", "?run=" + encodeURIComponent(id));
  }
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
  // A parameter may carry a `tuned:` value: the setting optimised on the QSM-CI scoring phantom,
  // shown next to the method's usual `default:`. Only disclosed (submission page); the leaderboard
  // still ranks methods at their defaults.
  const plist = a.parameters || [];
  // Per-parameter tuned value for a dataset. `tuned` is either a scalar (legacy = in-silico) or a
  // per-dataset map { sim, invivo }. Returns the value only when it actually differs from the default.
  const tunedVal = (p, ds) => {
    let t = p.tuned;
    if (t == null) return null;
    if (typeof t === "object") t = t[ds];
    else if (ds !== "sim") t = null;   // a legacy scalar tuning applies to in-silico only
    return (t != null && String(t) !== String(p.default)) ? t : null;
  };
  const hasSim = plist.some((p) => tunedVal(p, "sim") != null);
  const hasIv  = plist.some((p) => tunedVal(p, "invivo") != null);
  const hasCs  = plist.some((p) => tunedVal(p, "chisep") != null);
  const cell = (v) => v != null
    ? `<span class="text-emerald-600 dark:text-emerald-400">⚙ ${v}</span>`
    : `<span class="text-gray-300 dark:text-gray-600">—</span>`;
  const params = plist.map((p) =>
    `<tr class="border-t border-gray-100 dark:border-gray-800">`
    + `<td class="py-1 pr-3 font-mono text-gray-700 dark:text-gray-300">${p.name}</td>`
    + `<td class="py-1 pr-3 tabular-nums text-gray-500 dark:text-gray-400">${p.default}</td>`
    + (hasSim ? `<td class="py-1 pr-3 tabular-nums">${cell(tunedVal(p, "sim"))}</td>` : "")
    + (hasIv  ? `<td class="py-1 pr-3 tabular-nums">${cell(tunedVal(p, "invivo"))}</td>` : "")
    + (hasCs  ? `<td class="py-1 pr-3 tabular-nums">${cell(tunedVal(p, "chisep"))}</td>` : "")
    + `<td class="py-1 text-gray-400 dark:text-gray-500">${p.description || ""}</td></tr>`
  ).join("");
  const th = (lab, tip) => `<th class="py-1 pr-3 font-normal"><span class="has-tip text-emerald-600 dark:text-emerald-400" data-tip="${tip}">${lab}</span></th>`;
  const paramHead = (hasSim || hasIv || hasCs)
    ? `<thead><tr class="text-left text-gray-400 dark:text-gray-500"><th class="py-1 pr-3 font-normal">parameter</th><th class="py-1 pr-3 font-normal">default</th>`
      + (hasSim ? th("⚙ tuned · in&nbsp;silico (2019)", "Parameters optimised on the in-silico (2019) scoring phantom, maximising xSIM. The leaderboard still ranks methods at their defaults.") : "")
      + (hasIv  ? th("⚙ tuned · in&nbsp;vivo (2016)", "Parameters optimised on the in-vivo (2016) challenge data (COSMOS reference), maximising xSIM.") : "")
      + (hasCs  ? th("⚙ tuned · χ-sep (2026)", "Parameters optimised on the χ-separation phantom, maximising source-separation xSIM.") : "")
      + `<th class="py-1 font-normal"></th></tr></thead>`
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
  for (const s of pipelineSteps(run)) if (bySlug[s]) cards.push(methodCard(bySlug[s]));
  el.innerHTML = cards.join('<div class="border-t border-gray-100 dark:border-gray-800 pt-2"></div>');
  el.style.display = cards.length ? "" : "none";
}

// ---- detail + viewer --------------------------------------------------------
// Default + tuned isolated runs for the current method, if both exist (drives the Defaults/Tuned
// toggle: switching swaps the metrics AND the NiiVue volumes, since each variant is its own run).
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
  // No descriptive badges/meta in the title (dataset / stage / mode / artifact were noise); keep only a
  // DNF status flag when relevant and the interactive Defaults/Tuned variant toggle.
  $("sub-badges").innerHTML =
    (run.status === "DNF" ? badge("DNF", "bg-red-50 text-red-600 ring-red-100 dark:bg-red-500/10 dark:text-red-400 dark:ring-red-500/20") : "") +
    variantToggleHTML();
  $("sub-badges").querySelectorAll("[data-variant-id]").forEach((b) =>
    b.addEventListener("click", () => selectRun(b.dataset.variantId)));
  $("sub-meta").innerHTML = "";
  renderMethodInfo();
  renderHowToRun();
  renderDatasetSwitch();
  renderChisepPhantomSwitch();
  // Metrics card: render the metric table now (tabs hidden), then fetch THIS run's per-region file
  // (results/<id>/regions.json via HF regions_url, or the local fallback) off the critical path and
  // reveal the Regions/Error tabs when it arrives. Guard against a fast run-switch resolving stale.
  runRegions = null;
  renderMetricsPanel();
  // A synthesised repro run has its per-region means published to the Hub (deterministic regions_url,
  // via loadRunRegions) AND a resource trace: draw the CPU/RAM graph, fold its summary (runtime /
  // peak-mem / avg-cpu) back onto the run so the reproducibility metrics table can list them, and pull
  // the regions block so the Regions tab works too. (No ground truth here, so the block is recon-only.)
  if (reproMode) {
    renderResources(run);
    const wantRegions = run;
    loadRunRegions(run).then((entry) => { if (run === wantRegions) { runRegions = entry; renderMetricsPanel(); } });
    const wantRes = run;
    fetch(run.resources_url, { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)).then((d) => {
      if (!d || run !== wantRes) return;
      if (d.t && d.t.length) run.runtime_s = d.t[d.t.length - 1];
      run.mem_peak_bytes = d.mem_peak_bytes; run.cpu_cores_avg = d.cpu_cores_avg; run.cpu_cores_max = d.cpu_cores_max;
      renderMetricsPanel();
    }).catch(() => {});
  } else {
    const wantRegions = run;
    loadRunRegions(run).then((entry) => { if (run === wantRegions) { runRegions = entry; renderMetricsPanel(); } });
    // Render the resource graph up front, independent of (and before) the WebGL/NiiVue viewer, so a
    // browser without WebGL2, or a run whose volumes fail to load, still shows the usage trace.
    renderResources(run);
  }

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
    defaultDragMode = nv.opts.dragMode;   // remember the boot dragMode (contrast) so the Pan toggle can restore it
    // Shift+scroll = zoom the 2D view; shift+drag already pans natively (NiiVue routes shift+left-drag
    // to its center-button pan handler). NiiVue's own wheel handler ignores modifiers and only zooms
    // in dragMode 'pan' (which would kill plain slice-scrolling), so we gate zoom on Shift ourselves.
    // Capture phase on the wrapper: with Shift we do the zoom and stop the event before NiiVue's
    // canvas listener fires (else it would also scroll a slice); without Shift we let it through.
    (canvas.parentElement || canvas).addEventListener("wheel", (e) => {
      if (!e.shiftKey) return;                 // plain scroll → NiiVue changes slice, unchanged
      e.preventDefault(); e.stopPropagation();
      // Mirror NiiVue's zoom-about-crosshair math (pan2Dxyzmm[3] is the 2D zoom scale).
      const dir = e.deltaY < 0 ? 1 : -1;       // scroll up → zoom in
      let zoom = nv.scene.pan2Dxyzmm[3] * (1 + 0.1 * dir);
      zoom = Math.round(zoom * 10) / 10;
      if (zoom < 0.1) return;                   // don't invert/collapse the view
      const dz = nv.scene.pan2Dxyzmm[3] - zoom;
      nv.scene.pan2Dxyzmm[3] = zoom;
      const mm = nv.frac2mm(nv.scene.crosshairPos);
      nv.scene.pan2Dxyzmm[0] += dz * mm[0];
      nv.scene.pan2Dxyzmm[1] += dz * mm[1];
      nv.scene.pan2Dxyzmm[2] += dz * mm[2];
      nv.drawScene();
    }, { capture: true, passive: false });
    nv.addColormap("errpos", ERR_POS_CMAP);   // signed error map: over-estimate (red), under-estimate (blue)
    nv.addColormap("errneg", ERR_NEG_CMAP);
    nv.setSliceType(nv.sliceTypeMultiplanar);
    wireControls();
  }
  // New run: the base map (recon/truth) + source selection carry over; refreshView() rebuilds the
  // resident volume set when run.id changes.
  const hasError = !run.volumes || !!run.volumes.error;  // HF-backed runs advertise which volumes exist
  if (!hasError) showError = false;
  $("t-error").disabled = !hasError;
  $("t-error").checked = showError;
  // Harmonization runs have no ground truth / error, so drop the error overlay.
  if (reproMode) $("t-error").closest("label")?.classList.add("hidden");
  // The base layer persists across run switches, so it has to be one THIS run actually has —
  // swapping acquisition on the same pipeline keeps you on Field map, but moving to a pipeline
  // without that stage (or off the harmonization track entirely) falls back to the reconstruction
  // rather than requesting a map that was never published.
  if (!layerAvailable(curBase)) curBase = "recon";
  // An intermediate carried over from the previous run needs its file CONFIRMED before the first
  // paint — the URL is derived from the pipeline id, so a column that DNF'd would otherwise 404 into
  // the "volumes aren't available" note. Probes are cached, so this awaits at most once per map.
  if ((curBase === "totalfield" || curBase === "localfield") && !await probeVolume(run.volumes[curBase])) curBase = "recon";
  setLayerActive(curBase);
  // Toggle the base-layer buttons AFTER setLayerActive (it rewrites every button's className): the
  // harmonization track is recon-only with a per-acq Magnitude reference, hide Ground-truth, show
  // Magnitude there; invert everywhere else (so switching back to a sim run restores Ground-truth).
  $("layer-tabs")?.querySelector('[data-layer="truth"]')?.classList.toggle("hidden", reproMode);
  $("layer-tabs")?.querySelector('[data-layer="magnitude"]')?.classList.toggle("hidden", !(reproMode && !!run.volumes?.magnitude));
  revealReproLayers(++layerToken);   // async: the intermediates appear once their file is confirmed
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
// or isolated runs sharing this run's job). Returns { rank, n, t } where t is 0..1 goodness for
// colour, or null when there's nothing to compare against.
// Every stage that outputs a susceptibility map competes in ONE rank pool: a pure dipole step, a
// combined bfr+dipole method (TGV, NeXtQSM, …) and an end-to-end method (iQSM, …) all produce a
// χ map scored against the same ground truth, so their ranks are computed against each other
// rather than per stage. The stage split stays for categorisation/navigation only.
const CHI_RANK_STAGES = new Set(["dipole", "bfr+dipole", "end-to-end"]);
const sameRankStage = (r, run) =>
  CHI_RANK_STAGES.has(run.stage) ? CHI_RANK_STAGES.has(r.stage) : r.stage === run.stage;
function metricRank(k) {
  const meta = METRICS[k], v = val(run, k);   // val() also reaches top-level fields (e.g. runtime_s)
  if (v == null) return null;
  // Composed pipelines are ranked within their OWN field-mapping (the leaderboard groups the same
  // way: it shows one field-mapping's bfr×dipole matrix at a time), so the denominator matches the
  // table you clicked from, not the full cross-field-mapping pool of ~845 pipelines.
  const sameGroup = (r) => phantomKey(r) === phantomKey(run) && (run.combo
    ? r.mode === "composed" && (r.combo?.field_mapping || "gt") === (run.combo.field_mapping || "gt")
    : r.mode === "isolated" && sameRankStage(r, run));
  const peers = allRuns.filter((r) => r.status !== "DNF" && sameGroup(r) && val(r, k) != null);
  if (peers.length < 2) return null;
  const higher = meta.better !== "lower";
  const rank = 1 + peers.filter((r) => (higher ? val(r, k) > v : val(r, k) < v)).length;
  const [lo, hi] = robustRange(peers.map((r) => val(r, k)));
  let t = hi === lo ? 0.5 : (v - lo) / (hi - lo);
  if (!higher) t = 1 - t;
  return { rank, n: peers.length, t };
}

// Rank `run` among comparable peers by an arbitrary accessor (r) => value; used for χ-separation,
// whose paired metrics (para_*/dia_*) and the derived Avg xSIM aren't plain METRICS keys. Same
// grouping/goodness logic as metricRank(). `higher` = higher-is-better. null if <2 peers to compare.
function rankBy(accessor, higher) {
  const v = accessor(run);
  if (v == null) return null;
  // Composed pipelines are ranked within their OWN field-mapping (the leaderboard groups the same
  // way: it shows one field-mapping's bfr×dipole matrix at a time), so the denominator matches the
  // table you clicked from, not the full cross-field-mapping pool of ~845 pipelines.
  const sameGroup = (r) => phantomKey(r) === phantomKey(run) && (run.combo
    ? r.mode === "composed" && (r.combo?.field_mapping || "gt") === (run.combo.field_mapping || "gt")
    : r.mode === "isolated" && sameRankStage(r, run));
  const peers = allRuns.filter((r) => r.status !== "DNF" && sameGroup(r) && accessor(r) != null);
  if (peers.length < 2) return null;
  const rank = 1 + peers.filter((r) => (higher ? accessor(r) > v : accessor(r) < v)).length;
  const [lo, hi] = robustRange(peers.map(accessor));
  let t = hi === lo ? 0.5 : (v - lo) / (hi - lo);
  if (!higher) t = 1 - t;
  return { rank, n: peers.length, t };
}

function renderChisepMetrics() {
  // χ-separation runs carry paired, source-specific metrics (para_*/dia_*), not the plain QSM keys.
  // Render them grouped by source: χ+ gets iron/vein metrics, χ− gets calcification metrics, and each
  // gets a leakage (cross-contamination) term.
  $("metrics-sub").textContent = "χ+ / χ− sources vs. ground truth";
  const mv = (k) => (r) => { const x = r.metrics ? r.metrics[k] : null; return x == null ? null : x; };
  const avgAcc = (r) => {
    const p = r.metrics ? r.metrics.para_xsim : null, d = r.metrics ? r.metrics.dia_xsim : null;
    return (p != null && d != null) ? (p + d) / 2 : null;
  };
  const avgMspeAcc = (r) => {
    const p = r.metrics ? r.metrics.para_mspe : null, d = r.metrics ? r.metrics.dia_mspe : null;
    return (p != null && d != null) ? (p + d) / 2 : null;
  };
  const rtAcc = (r) => (r.runtime_s == null ? null : r.runtime_s);
  const memAcc = (r) => (r.mem_peak_bytes == null ? null : r.mem_peak_bytes);
  const cpuAcc = (r) => (r.cpu_cores_avg == null ? null : r.cpu_cores_avg);
  const num = (v, fk) => v == null ? null
    : fk === "pct" ? v.toFixed(1) + "%" : fk === "xsim" ? fmt(v, "xsim")
    : fk === "sec" ? fmt(v, "runtime_s") : fk === "bytes" ? fmt(v, "mem_peak_bytes")
    : fk === "cores" ? fmt(v, "cpu_cores_avg") : v.toFixed(3);
  // rows: [label, accessor, formatKey, arrow, tip]: accessor(r) yields the value for run r (so peers
  // can be ranked the same way), arrow "↑" = higher-is-better.
  const groups = [
    [null, [["Avg MSPE", avgMspeAcc, "pct", "↓", "Mean of the χ+ and χ− per-ROI MSPE: the headline combined score (Ridani et al. 2026)."]]],
    ["χ+ paramagnetic (iron, veins)", [
      ["MSPE", mv("para_mspe"), "pct", "↓", "Per-ROI MSPE of χ+ over the iron nuclei + GM (mean squared %-error of ROI means). WM excluded (χ+ ~1 ppb → unstable %)."],
      ["xSIM", mv("para_xsim"), "xsim", "↑", "Structural similarity of χ+ vs ground truth."],
      ["NRMSE", mv("para_nrmse"), "pct", "↓", "Normalised RMS error of χ+ (%)."],
      ["DGM NRMSE", mv("para_nrmse_dgm"), "pct", "↓", "χ+ error in deep gray matter (iron)."],
      ["DGM linearity", mv("para_dgm_linearity"), "num", "↓", "|1 − slope| of χ+ across DGM iron regions; 0 = perfect iron quantification."],
      ["Vein NRMSE", mv("para_nrmse_blood"), "pct", "↓", "χ+ error in venous blood."],
      ["Ca leak", mv("para_calc_leak"), "num", "↓", "Mean |χ+| in the calcification (should be ~0): calcium wrongly bleeding into the paramagnetic map."],
      ["χ−→χ+ leak", mv("para_leak"), "num", "↓", "Regression slope of χ+ on the χ− ground truth: how much diamagnetic signal bleeds into the paramagnetic map. 0 = clean; positive = leakage; negative = over-separation (χ+ suppressed where χ− is strong)."],
    ]],
    ["χ− diamagnetic (calcium, myelin)", [
      ["MSPE", mv("dia_mspe"), "pct", "↓", "Per-ROI MSPE of χ− over the fibre-bundle atlas WM sub-ROIs (Ridani et al. 2026, Fig 3): the metric anisotropy makes hardest."],
      ["xSIM", mv("dia_xsim"), "xsim", "↑", "Structural similarity of χ− vs ground truth."],
      ["NRMSE", mv("dia_nrmse"), "pct", "↓", "Normalised RMS error of χ− (%)."],
      ["Ca dev", mv("dia_calc_moment_dev"), "num", "↓", "Deviation of the recovered calcification's susceptibility moment."],
      ["Streaking", mv("dia_calc_streak"), "num", "↓", "Streaking-artifact level around the calcification."],
      ["MEV", mv("dia_mev"), "pct", "↓", "Maximum error variation (Ridani et al. 2026, Fig 5): fractional drop in χ− error from fibres parallel to B0 to perpendicular. A diagnostic of orientation-dependent error, not a ranking metric."],
      ["Fe leak", mv("dia_iron_leak"), "num", "↓", "Mean |χ−| in DGM/veins (should be ~0): iron wrongly bleeding into the diamagnetic map."],
      ["χ+→χ− leak", mv("dia_leak"), "num", "↓", "Regression slope of χ− on the χ+ ground truth: how much paramagnetic signal bleeds into the diamagnetic map. 0 = clean; positive = leakage; negative = over-separation (χ− suppressed where χ+ is strong)."],
    ]],
    ["Resources", [
      ["Runtime", rtAcc, "sec", "↓", "Wall-clock runtime."],
      ["Peak memory", memAcc, "bytes", "↓", "Peak resident memory (max RSS) sampled while the method runs: the RAM it needs to fit."],
      ["Avg CPU", cpuAcc, "cores", "↑", "Average CPU cores busy over the run (CPU-time ÷ wall-time): how well it parallelises. ~1 = single-threaded."],
    ]],
  ];
  let html = "";
  for (const [header, rows] of groups) {
    if (header) html += `<tr><td colspan="3" class="pt-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">${header}</td></tr>`;
    for (const [label, acc, fk, arrow, tip] of rows) {
      const v = acc(run);
      if (v == null) continue;
      const hero = label === "Avg MSPE";
      const rk = rankBy(acc, arrow === "↑");
      const rankCell = rk
        ? `<span class="inline-block rounded-md px-1.5 py-0.5 text-xs font-semibold text-white shadow-sm" style="background:${heatScale(rk.t)}" data-tip="Rank ${rk.rank} of ${rk.n} χ-separation methods for ${label}">#${rk.rank}<span class="opacity-70"> / ${rk.n}</span></span>`
        : `<span class="text-gray-300 dark:text-gray-600">—</span>`;
      html += `<tr>
        <td class="whitespace-nowrap py-2 text-gray-500 dark:text-gray-400"><span class="has-tip" data-tip="${tip.replace(/"/g, "&quot;")}">${label}</span> <span class="text-gray-300 dark:text-gray-600" title="${arrow === "↑" ? "higher" : "lower"} is better">${arrow}</span></td>
        <td class="py-2 text-right tabular-nums ${hero ? "font-bold text-gray-900 dark:text-gray-100" : "font-medium text-gray-700 dark:text-gray-300"}">${num(v, fk)}</td>
        <td class="py-2 pl-3 text-right">${rankCell}</td>
      </tr>`;
    }
  }
  $("metrics-body").innerHTML = html || `<tr><td class="py-3 text-gray-400">No metrics for this run.</td></tr>`;
}
function renderMetrics() {
  // R2′ generators are single-map runs (r2prime vs the phantom's true R2′): the default renderer
  // fits (their nrmse/nrmse_detrend/correlation/xsim are plain METRICS keys); only χ-separation
  // outputs (isolated methods AND the GRE-only composed combos) get the paired χ+/χ− table.
  if ((run.domain === "chisep" || run.stage === "chi-separation") && run.stage !== "r2prime-generation") { renderChisepMetrics(); return; }
  $("metrics-sub").textContent = run.stage === "r2prime-generation"
    ? "Generated R2′ vs. the phantom's true (spin-echo-derived) R2′"
    : run.mode === "composed" ? "Final χ map vs. ground truth" : `${run.artifact || "output"} vs. ground truth`;
  // Include runtime_s (a top-level field, not under run.metrics) via val(), so it's ranked alongside
  // the accuracy metrics. Object.keys(METRICS) keeps it last, matching its registry order.
  const order = Object.keys(METRICS).filter((k) => val(run, k) != null);
  const groupLabel = run.combo ? "composed pipelines"
    : CHI_RANK_STAGES.has(run.stage) ? "isolated χ-map methods (dipole, bfr+dipole, end-to-end)"
    : `isolated ${STAGE_LABEL[run.stage] || run.stage} methods`;
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

// ---- per-region stats (Metrics card: Metrics | Regions | Error tabs) ------------------------
// Fed by this run's results/<id>/regions.json (loadRunRegions): descriptive susceptibility stats
// (n/mean/std/median, ppm) for the run and its paired ground truth inside every segmented region,
// under the run's own score mask.
const REGION_ORDER = ["1", "2", "3", "4", "5", "6", "7", "9", "8", "10", "11", "16", "13", "14", "15"];
const p3 = (v) => (v < 0 ? "−" : "") + Math.abs(v).toFixed(3);

function renderMetricsPanel() {
  if (reproMode) return renderReproStats();
  const entry = runRegions;
  const tabs = $("metrics-tabs");
  // Undo any repro relabelling: on the sim/accuracy path the first tab is "Metrics" and Error is shown.
  const mBtn = tabs?.querySelector('[data-mtab="metrics"]'); if (mBtn) mBtn.textContent = "Metrics";
  tabs?.querySelector('[data-mtab="error"]')?.classList.remove("hidden");
  tabs.classList.toggle("hidden", !entry);
  // Fall back to the metric table whenever there's no usable region entry: this run has none, OR
  // the sidecar hasn't finished its lazy load yet. `metricsTab` (which may be a deep-linked
  // 'regions'/'error') is left UNTOUCHED, so once regions arrive this re-runs and honours it.
  const tab = entry ? metricsTab : "metrics";
  tabs.querySelectorAll("[data-mtab]").forEach((b) => {
    const on = b.dataset.mtab === tab;
    ["bg-white", "shadow-sm", "text-gray-900", "dark:bg-gray-700", "dark:text-gray-100"].forEach((c) => b.classList.toggle(c, on));
    ["text-gray-500", "dark:text-gray-400"].forEach((c) => b.classList.toggle(c, !on));
  });
  const table = tab === "metrics";
  $("metrics-table-wrap").classList.toggle("hidden", !table);
  $("metrics-regions-wrap").classList.toggle("hidden", table);
  if (table) renderMetrics();
  else renderRegionTable(entry, tab === "error");
}

function renderRegionTable(entry, errorMode) {
  // χ-sep runs carry one block per component (para/dia); QSM runs a single `chi` block.
  const comps = entry.chi ? null : ["para", "dia"].filter((k) => entry[k]);
  if (comps && !entry[regionComp]) regionComp = comps[0];
  const block = entry.chi || entry[regionComp];
  if (!block || !block.recon) {   // entry present but no usable component (e.g. empty/partial sidecar)
    $("metrics-sub").textContent = "Per-region statistics unavailable for this run.";
    $("metrics-regions-wrap").innerHTML = `<p class="py-3 text-sm text-gray-400">No regional statistics for this run.</p>`;
    return;
  }
  $("metrics-sub").textContent = errorMode
    ? "Per-region quantification error: this run − ground truth, within the run's valid support (ppm)."
    : "Susceptibility per segmented region: this run vs ground truth, within the run's valid support (ppm).";
  const ids = REGION_ORDER.filter((k) => block.recon[k] && block.truth[k])
    .concat(Object.keys(block.recon).filter((k) => !REGION_ORDER.includes(k) && block.truth[k]).sort());
  let html = "";
  if (comps) {
    html += `<div class="mb-3 inline-flex rounded-lg bg-gray-100 p-0.5 text-xs dark:bg-gray-800">` + comps.map((k) =>
      `<button data-comp="${k}" class="rounded-md px-2.5 py-1 font-medium ${k === regionComp
        ? "bg-white shadow-sm text-gray-900 dark:bg-gray-700 dark:text-gray-100" : "text-gray-500 dark:text-gray-400"}">${k === "para" ? "χ+ para" : "χ− dia"}</button>`).join("") + `</div>`;
  }
  if (!ids.length) {
    $("metrics-regions-wrap").innerHTML = html + `<p class="py-3 text-sm text-gray-400">No regional statistics for this run.</p>`;
  } else if (errorMode) {
    const rows = ids.map((k) => {
      const rc = block.recon[k], gt = block.truth[k];
      // Divide by |gt.mean| so the % keeps the sign of Δ mean: for a diamagnetic (negative-mean)
      // region (white matter, bone), dividing by the raw negative mean would flip the sign, showing
      // an over-estimate as a negative %, contradicting the Δ mean column right beside it.
      return { k, d: rc.mean - gt.mean, dm: rc.median - gt.median,
               pct: Math.abs(gt.mean) >= 0.005 ? (rc.mean - gt.mean) / Math.abs(gt.mean) * 100 : null, n: rc.n };
    });
    const dmax = Math.max(...rows.map((r) => Math.abs(r.d))) || 1;
    html += `<table class="w-full text-[11px]"><thead><tr class="text-[10px] uppercase tracking-wide text-gray-400 dark:text-gray-500">
      <th class="pb-1.5 text-left font-medium">Region</th><th class="whitespace-nowrap pb-1.5 pl-2 text-right font-medium" data-tip="Mean of this run − mean of ground truth in the region (ppm).">Δ mean</th>
      <th class="whitespace-nowrap pb-1.5 pl-2 text-right font-medium" data-tip="Median of this run − median of ground truth (ppm).">Δ med</th>
      <th class="whitespace-nowrap pb-1.5 pl-2 text-right font-medium" data-tip="Δ mean as a percentage of the ground-truth mean; blank where the truth mean is near zero (unstable denominator).">Δ %</th>
      <th class="pb-1.5 pl-2 text-left font-medium" style="width:4.25rem"></th></tr></thead><tbody class="divide-y divide-gray-100 dark:divide-gray-800">`;
    rows.forEach((r) => {
      // sqrt scaling: one huge outlier (e.g. the calcification) would otherwise flatten every
      // other region's bar to invisibility on a linear scale.
      const bw = Math.sqrt(Math.abs(r.d) / dmax) * 50;
      const wPos = r.d > 0 ? bw : 0, wNeg = r.d < 0 ? bw : 0;
      html += `<tr>
        <td class="py-1.5 pr-1 leading-tight text-gray-500 dark:text-gray-400"><span data-tip="n=${r.n} voxels in this run's support">${block.labels[r.k] || "label-" + r.k}</span></td>
        <td class="whitespace-nowrap py-1.5 pl-2 text-right tabular-nums font-medium ${Math.abs(r.d) >= 0.01 ? "text-gray-900 dark:text-gray-100" : "text-gray-600 dark:text-gray-300"}">${p3(r.d)}</td>
        <td class="whitespace-nowrap py-1.5 pl-2 text-right tabular-nums text-gray-600 dark:text-gray-300">${p3(r.dm)}</td>
        <td class="whitespace-nowrap py-1.5 pl-2 text-right tabular-nums text-gray-600 dark:text-gray-300">${r.pct == null ? ", " : (r.pct > 0 ? "+" : "−") + Math.abs(r.pct).toFixed(0) + "%"}</td>
        <td class="py-1.5 pl-2" style="width:4.25rem"><div data-tip="under- / over-estimation vs ground truth (bars √-scaled to the largest |Δ mean|)" style="display:flex;align-items:center;height:8px;width:100%">
          <div style="flex:1;display:flex;justify-content:flex-end"><div style="height:8px;border-radius:3px 0 0 3px;width:${wNeg * 2}%;background:#3b82f6;opacity:.7"></div></div>
          <div style="width:1px;height:12px;background:#94a3b8;opacity:.55"></div>
          <div style="flex:1"><div style="height:8px;border-radius:0 3px 3px 0;width:${wPos * 2}%;background:#e11d48;opacity:.7"></div></div>
        </div></td></tr>`;
    });
    html += `</tbody></table><p class="mt-2 text-[11px] text-gray-400"><span style="color:#3b82f6">blue</span> = underestimates the region's χ, <span style="color:#e11d48">red</span> = overestimates.</p>`;
    $("metrics-regions-wrap").innerHTML = html;
  } else {
    // Three columns for a narrow card: Region | This run | Ground truth. Each value cell stacks
    // "mean ±std" over a smaller "med …" line, so the mean/median/std all fit without five columns.
    const cell = (s, hero) => `<td class="py-1.5 pl-2 text-right align-top tabular-nums">`
      + `<div class="whitespace-nowrap ${hero ? "font-medium text-gray-900 dark:text-gray-100" : "text-gray-600 dark:text-gray-300"}">${p3(s.mean)} <span class="font-normal text-gray-400">±${s.std.toFixed(3)}</span></div>`
      + `<div class="whitespace-nowrap text-[10px] text-gray-400">med ${p3(s.median)}</div></td>`;
    html += `<table class="w-full text-[11px]"><thead><tr class="text-[10px] uppercase tracking-wide text-gray-400 dark:text-gray-500">
      <th class="pb-1.5 text-left font-medium">Region</th>
      <th class="whitespace-nowrap pb-1.5 pl-2 text-right font-medium" data-tip="This run: mean ± std and median (below) of χ over the region (ppm).">This run</th>
      <th class="whitespace-nowrap pb-1.5 pl-2 text-right font-medium" data-tip="Ground truth in the same voxels: mean ± std and median (below) (ppm).">Ground truth</th></tr></thead><tbody class="divide-y divide-gray-100 dark:divide-gray-800">`;
    ids.forEach((k) => {
      const rc = block.recon[k], gt = block.truth[k];
      html += `<tr>
        <td class="py-1.5 pr-1 align-top leading-tight text-gray-500 dark:text-gray-400"><span data-tip="n=${rc.n} voxels in this run's support">${block.labels[k] || "label-" + k}</span></td>
        ${cell(rc, true)}${cell(gt, false)}</tr>`;
    });
    html += `</tbody></table>`;
    $("metrics-regions-wrap").innerHTML = html;
  }
  $("metrics-regions-wrap").querySelectorAll("[data-comp]").forEach((b) =>
    b.addEventListener("click", () => { regionComp = b.dataset.comp; renderRegionTable(entry, errorMode); }));
}

// ---- controls ---------------------------------------------------------------
const cap = (s) => s[0].toUpperCase() + s.slice(1);
const baseVol = () => activeBaseVol || nv.volumes[0];
function setLayerActive(layer) {
  $("layer-tabs").querySelectorAll("button").forEach((t) => {
    const wasHidden = t.classList.contains("hidden");   // per-track button visibility (set on run-load);
    t.className = "rounded-md px-3 py-1 transition " +   // reassigning className would otherwise un-hide it
      (t.dataset.layer === layer ? "bg-white shadow-sm text-gray-900 dark:bg-gray-700 dark:text-gray-100" : "text-gray-500 hover:text-gray-700 dark:text-gray-400");
    if (wasHidden) t.classList.add("hidden");
  });
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

// Signed error-map colormaps: over-estimate (recon>truth) ramps transparent→red→yellow, under-estimate
// ramps transparent→blue→cyan. Alpha starts at 0 so the inner window bound (cal_min) is a hard
// transparency floor (errors below it, including exact zero and the masked background, don't render at all)
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
  // base map colormap (recon/truth): compact dropdown above this control's Auto button
  baseCtl = makeWindowControl(() => nv, () => baseVol(), {
    value: "gray",
    options: [["gray", "Gray"], ["viridis", "Viridis"], ["plasma", "Plasma"], ["hot", "Hot"], ["cool", "Cool"]],
    // apply to every resident base map so the colormap persists across recon/truth/χ± toggles
    onChange: (v) => { nv.volumes.forEach((vol) => { if (vol.__role === "base") vol.colormap = v; }); nv.updateGLVolume(); },
  });
  // error overlay colormap: dropdown above the error window's Auto button; drives setErrorColormap
  errorCtl = makeWindowControl(() => nv, () => activeErrVol, {
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
      refreshView();   // toggles opacity to the χ± source's resident volumes; no re-fetch
    }));
  $("t-error").addEventListener("change", (e) => { showError = e.target.checked; refreshView(); });
  $("view-tabs").querySelectorAll("button").forEach((t) =>
    t.addEventListener("click", () => { setViewActive(t.dataset.view); nv.setSliceType(nv["sliceType" + cap(t.dataset.view)]); }));
  $("t-colorbar").addEventListener("change", (e) => { nv.opts.isColorbar = e.target.checked; nv.drawScene(); });
  $("t-crosshair").addEventListener("change", (e) => { nv.setCrosshairWidth(e.target.checked ? 0.75 : 0); });
  $("t-interp").addEventListener("change", (e) => { nv.setInterpolation(!e.target.checked); nv.drawScene(); });
  $("opacity").addEventListener("input", (e) => {
    const o = parseFloat(e.target.value);
    if (activeErrVol) activeErrVol.opacity = o;   // slider drives the error overlay only
    $("opacity-val").textContent = Math.round(o * 100) + "%";
    nv.updateGLVolume();
  });
  const redrawAll = () => winControls.forEach((c) => c.redraw());
  window.addEventListener("resize", redrawAll);
  // Fullscreen: take the whole viewer section (canvas + histogram + controls) fullscreen, not just the
  // canvas, so windowing/tabs stay usable. NiiVue's ResizeObserver on the canvas wrapper repaints the GL
  // canvas when it grows; the histograms only relayout on window resize, so nudge them after the switch.
  const fsSection = $("viewer-section"), fsBtn = $("fullscreen-btn");
  fsBtn?.addEventListener("click", () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else fsSection?.requestFullscreen?.();
  });
  document.addEventListener("fullscreenchange", () => {
    const on = document.fullscreenElement === fsSection;
    $("fs-icon-open").classList.toggle("hidden", on);
    $("fs-icon-close").classList.toggle("hidden", !on);
    fsBtn.title = on ? "Exit fullscreen" : "Fullscreen, click Pan/Zoom, or Shift+scroll / Shift+drag";
    setTimeout(() => { redrawAll(); nv?.drawScene(); }, 60);
  });
  // Pan + zoom buttons next to Fullscreen: plain left-click pan (no Shift), and step/reset zoom of the
  // 2D view. Zoom drives nv.scene.pan2Dxyzmm[3] (the 2D zoom scale), the same knob the Shift+scroll
  // handler above uses, NOT volScaleMultiplier (that's the 3D-render zoom). Pan toggles the NiiVue
  // dragMode between the default (contrast) and pan (nv.dragModes.pan = 3), so left-drag pans while ON.
  // Pan: NiiVue pans natively on Shift+left-drag, its mousedown routes Shift+left to the center-button
  // (pan) handler, and mouseMove then pans off the stored center-down state (no Shift re-check). So the
  // Pan toggle simply replays a plain left mousedown AS Shift+left: real panning, crosshair/slice
  // untouched, and the wheel stays slice-scrolling (NiiVue's dragMode='pan' would hijack it to zoom).
  // NiiVue's own canvas (nv.gl.canvas); the `canvas` var from loadRun() isn't in this function's scope.
  const glCanvas = nv.gl.canvas;
  const panBtn = $("pan-btn");
  panBtn?.addEventListener("click", () => {
    panOn = !panOn;
    panBtn.classList.toggle("is-on", panOn);
    glCanvas.style.cursor = panOn ? "grab" : "";
    panBtn.title = panOn ? "Pan: on, left-drag to pan (click to turn off)" : "Pan, enable left-drag panning";
  });
  // Capture phase on an ancestor fires before NiiVue's canvas mousedown listener; block the real event
  // and re-dispatch it to the canvas with shiftKey set. The _synthPan guard keeps the replayed event
  // (which also passes through this capture listener) from re-entering.
  let _synthPan = false;
  (glCanvas.parentElement || glCanvas).addEventListener("mousedown", (e) => {
    if (!panOn || _synthPan || e.button !== 0 || e.shiftKey) return;
    e.stopImmediatePropagation(); e.preventDefault();
    _synthPan = true;
    glCanvas.dispatchEvent(new MouseEvent("mousedown", {
      bubbles: true, cancelable: true, view: window,
      clientX: e.clientX, clientY: e.clientY, screenX: e.screenX, screenY: e.screenY,
      button: 0, buttons: 1, shiftKey: true,
    }));
    _synthPan = false;
    glCanvas.style.cursor = "grabbing";
  }, { capture: true });
  window.addEventListener("mouseup", () => { if (panOn) glCanvas.style.cursor = "grab"; });
  const zoom2D = (factor) => {
    if (!nv) return;
    let zoom = nv.scene.pan2Dxyzmm[3] * factor;
    zoom = Math.min(8, Math.max(0.5, zoom));            // clamp to a sane 2D-zoom range
    zoom = Math.round(zoom * 100) / 100;
    // Zoom about the crosshair, mirroring the Shift+scroll handler's math.
    const dz = nv.scene.pan2Dxyzmm[3] - zoom;
    nv.scene.pan2Dxyzmm[3] = zoom;
    const mm = nv.frac2mm(nv.scene.crosshairPos);
    nv.scene.pan2Dxyzmm[0] += dz * mm[0];
    nv.scene.pan2Dxyzmm[1] += dz * mm[1];
    nv.scene.pan2Dxyzmm[2] += dz * mm[2];
    nv.drawScene();
  };
  $("zoom-in-btn")?.addEventListener("click", () => zoom2D(1.2));
  $("zoom-out-btn")?.addEventListener("click", () => zoom2D(1 / 1.2));
  $("zoom-reset-btn")?.addEventListener("click", () => {
    if (!nv) return;
    if (typeof nv.scene.pan2Dxyzmm !== "undefined") nv.scene.pan2Dxyzmm = [0, 0, 0, 1];   // reset 2D pan + zoom
    if (nv.uiData) nv.uiData.pan2Dxyzmm = [0, 0, 0, 1];        // clear the in-flight working copy too
    if ("volScaleMultiplier" in nv) nv.volScaleMultiplier = 1; // also clear any 3D-render zoom
    nv.drawScene();
  });
  // theme toggle flips html.dark without reloading; recolour every histogram
  new MutationObserver(redrawAll).observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  nv.setInterpolation(true);
  setViewActive("multiplanar");
}

// Volumes are served from the Hugging Face Hub (run.volumes[kind]); fall back to local results/<id>/ for dev.
// R2′ generators share the chisep DOMAIN (they only run on chisep-track phantoms) but are NOT
// χ-separation runs: one single-map output (r2prime, Hz), no χ+/χ− pair. Composed GRE-only combos
// (stage "r2prime-generation+chi-separation") DO produce the pair, so only the bare generator stage
// is excluded here.
const isR2pRun = () => run && run.stage === "r2prime-generation";
const isChisepRun = () => run && (run.domain === "chisep" || run.stage === "chi-separation") && !isR2pRun();
// χ-separation writes a second set of volumes for the χ− source with a "-dia" suffix
// (recon-dia.nii.gz, truth-dia.nii.gz, error-dia.nii.gz); the χ+ set uses the plain names. HF-backed
// runs expose each as its own run.volumes key (recon / recon-dia / …); dev falls back to local files.
const volKey = (kind, comp) => kind + (comp === "dia" ? "-dia" : "");
// Every map the layer strip can put underneath (anything else means the reconstruction).
const BASE_KINDS = new Set(["truth", "magnitude", "totalfield", "localfield"]);
function volUrlFor(kind, comp) {
  const key = volKey(kind, comp);
  if (run && run.volumes && run.volumes[key]) return run.volumes[key];
  const local = run && localTruth.get(`${run.id}/${key}`);
  return local || baseUrl + key + ".nii.gz";
}
// Dev fallback for the ground truth: pipeline.py stages ONE truth per phantom under results/_truth/
// and leaves a `truth.ref` pointer (path relative to results/) in the run dir instead of a per-run
// copy. Resolve the pointer once per run so the local truth layer still loads; a run without one
// (a legacy per-run truth.nii.gz) keeps the plain path.
const localTruth = new Map();   // `${run.id}/${key}` -> resolved local URL
async function resolveLocalTruth(kind, comp) {
  const key = volKey(kind, comp);
  if (kind !== "truth" || !run || (run.volumes && run.volumes[key]) || localTruth.has(`${run.id}/${key}`)) return;
  try {
    const r = await fetch(baseUrl + key + ".ref");
    if (r.ok) localTruth.set(`${run.id}/${key}`, "results/" + (await r.text()).trim());
  } catch { /* no pointer: keep the per-run path */ }
}
const runHasError = () => !run.volumes || !!run.volumes.error;

// ── Harmonization intermediates: field map + local field ───────────────────────────────────────
// These are the only optional layers whose presence can't be read off the run object alone: the URL
// is derivable from the pipeline id, but a column that DNF'd (or an acquisition whose intermediates
// haven't been published yet) has no file behind it. So HEAD-probe once per URL, cache the verdict,
// and reveal the tab only on a hit — a miss leaves the tab absent, exactly like Ground truth on a
// track with no ground truth. HF's `resolve/` endpoint answers HEAD with CORS headers, and any
// failure (404, offline, CORS) is read as "not available".
const volProbes = new Map();   // url -> Promise<boolean>
const probeVolume = (url) => {
  if (!volProbes.has(url)) volProbes.set(url, fetch(url, { method: "HEAD" }).then((r) => r.ok).catch(() => false));
  return volProbes.get(url);
};
// Whether a base layer exists for the open run — the same rule the tab strip is toggled by: ground
// truth on every track that has one, and the magnitude reference plus the two intermediates only on
// the harmonization track, and only when the run advertises that URL.
const layerAvailable = (kind) => kind === "recon" ? true
  : kind === "truth" ? !reproMode
  : reproMode && !!run?.volumes?.[kind];
// Bumped on every run load so a probe that resolves late can't un-hide a tab on a run since replaced.
let layerToken = 0;
// Which stage of the open pipeline wrote each intermediate — named in the tab's tooltip, since the
// map belongs to that ONE method rather than to the pipeline as a whole.
// Indexed by position in the pipeline id, the same way the URLs above are built, so the tooltip and
// the file it describes can't drift. (Not run.combo: a 2-part pipeline leaves that null — see
// makeReproRun — but its pipeline id still names both steps.)
const INTERMEDIATE_STAGE = {
  totalfield: [0, "Total field, written by the field-mapping stage"],
  localfield: [1, "Local (tissue) field, written by the background-removal stage"],
};
async function revealReproLayers(token) {
  const btns = ["totalfield", "localfield"].map((k) => [k, $("layer-tabs")?.querySelector(`[data-layer="${k}"]`)]);
  for (const [, b] of btns) b?.classList.add("hidden");   // hide synchronously; reveal on a confirmed hit
  for (const [kind, btn] of btns) {
    const url = reproMode ? run?.volumes?.[kind] : null;
    if (!btn || !url) continue;
    const ok = await probeVolume(url);
    if (token !== layerToken) return;                     // a different run is open now
    if (!ok) continue;
    const [step, label] = INTERMEDIATE_STAGE[kind];
    const by = run.pipelineId?.split("+")[step];
    btn.title = by ? `${label} (${algoName(by)})` : label;
    btn.classList.remove("hidden");
  }
}
const volComps = () => (isChisepRun() ? ["para", "dia"] : ["para"]);
const residentByUrl = (u) => nv.volumes.find((v) => v.url === u);

// Per-source display window, applied to susceptibility maps only (the recon and its ground truth):
// χ+ [0,0.1], χ− [0,0.05]; plain χ maps ±0.1 ppm. Every other map — the magnitude structural
// reference, field maps, R2′ — carries arbitrary units a ppm window would black out, so it gets the
// robust auto window instead.
const isChiMap = (kind) => kind === "recon" || kind === "truth";
function windowFor(vol, kind, comp) {
  if (!isChiMap(kind)) autoWin(vol);
  else if (run.kind === "chi") { vol.cal_min = -0.1; vol.cal_max = 0.1; }
  else if (isChisepRun()) { vol.cal_min = 0; vol.cal_max = comp === "dia" ? 0.05 : 0.1; }
  else autoWin(vol);
}

// Load one candidate map into nv.volumes (hidden) and tag it, unless already resident. `role` is
// "base" (recon/truth) or "error". All bases are loaded before any error so the error stays on top.
async function ensureVolume(role, kind, comp) {
  await resolveLocalTruth(kind, comp);
  const url = volUrlFor(kind, comp);
  let v = residentByUrl(url);
  if (v) return v;
  const cmap = role === "error"
    ? (errorCtl.cmapSelect.value === "diverging" ? "errpos" : errorCtl.cmapSelect.value)
    : (baseCtl.cmapSelect.value || "gray");
  if (!nv.volumes.length) await nv.loadVolumes([{ url, colormap: cmap, opacity: 0 }]);
  else await nv.addVolumeFromUrl({ url, colormap: cmap, opacity: 0 });
  v = residentByUrl(url);
  if (!v) return null;
  v.__role = role; v.__kind = kind; v.__comp = comp;
  if (role === "base") windowFor(v, kind, comp);
  return v;
}

// Load every candidate map for this run once: all bases first (they sit below), then the error
// overlays. Kicked off in the background after the first base paints; awaited before an error shows.
async function preloadAll() {
  // magnitude = the harmonization per-acq input reference (only repro runs carry volumes.magnitude);
  // truth = only sim/chisep. An HF-backed run advertises exactly which maps exist, so skip the ones it
  // doesn't rather than spending a 404 on each; a dev run with no `volumes` map tries them all and lets
  // the try/catch swallow the misses. The field-map / local-field intermediates are deliberately NOT
  // preloaded — they're a deep-dive click, not the default view, and each is another brain volume.
  for (const comp of volComps())
    for (const kind of ["recon", "truth", "magnitude"]) {
      if (run.volumes && kind !== "recon" && !run.volumes[volKey(kind, comp)]) continue;
      try { await ensureVolume("base", kind, comp); } catch (_) { /* 404 → skip */ }
    }
  if (runHasError())
    for (const comp of volComps()) { try { await ensureVolume("error", "error", comp); } catch (_) { /* skip */ } }
}

// Toggle opacity so only the active base (opacity 1) and, if shown, the active error overlay (slider
// opacity) render; every other resident volume is hidden (opacity 0). No fetch; this is the switch.
function applyOpacities() {
  const oErr = parseFloat($("opacity").value);
  for (const v of nv.volumes) {
    if (v.__role === "error") v.opacity = (v === activeErrVol ? oErr : 0);
    else v.opacity = (v === activeBaseVol ? 1 : 0);
  }
}

// Reconcile the viewer with (curBase, chisepComp, showError) by toggling opacity on the resident,
// preloaded volumes; a switch does NOT re-fetch. Only the first view of a run (or a not-yet-preloaded
// map) actually loads data. On a new run the previous run's volumes are dropped and the set rebuilt.
async function refreshView() {
  const baseKind = BASE_KINDS.has(curBase) ? curBase : "recon";
  const runChanged = residentRunId !== run.id;
  if (runChanged) {
    [...nv.volumes].forEach((v) => nv.removeVolumeByUrl(v.url));
    residentRunId = run.id; activeBaseVol = activeErrVol = null; preloadPromise = null;
  }
  const needErr = showError && runHasError();
  const pending = !residentByUrl(volUrlFor(baseKind, chisepComp))
    || (needErr && !residentByUrl(volUrlFor("error", chisepComp)));
  if (pending) setLoading(true);
  try {
    activeBaseVol = await ensureVolume("base", baseKind, chisepComp);   // the visible map (await)
    if (!activeBaseVol) throw new Error("base volume unavailable");     // → loadRun shows the fallback note
    if (!preloadPromise) preloadPromise = preloadAll();                 // background-load the rest
    // Reveal the error windowing section BEFORE setErrorColormap() so its canvas has a non-zero size
    // when the histogram first draws (a hidden display:none element reports clientWidth 0).
    $("win-error-section").classList.toggle("hidden", !showError);
    if (needErr) { await preloadPromise; activeErrVol = await ensureVolume("error", "error", chisepComp); }
    else activeErrVol = null;
  } finally { if (pending) setLoading(false); }
  applyOpacities();
  if (activeErrVol) setErrorColormap();   // colormap (+ diverging negative), window, magnitude mode
  baseCtl.setup();                        // reframe the base histogram/window for the active map
  nv.updateGLVolume();
  // A new run can have a different geometry (in-vivo 160³ vs in-silico 164×205×205, or a harmonization
  // brain with a different affine). NiiVue keeps its 2D pan/zoom and crosshair across volume swaps, so a
  // fresh volume renders through the previous one's framing, off-centre, worse each toggle. Recentre
  // whenever the run changes. Reset BOTH the committed scene pan AND the working-copy uiData.pan2Dxyzmm
  // (the live drag/zoom buffer): resetting only scene lets a prior pan get re-applied on the next draw.
  if (runChanged) {
    try {
      nv.scene.pan2Dxyzmm = [0, 0, 0, 1];
      if (nv.uiData) nv.uiData.pan2Dxyzmm = [0, 0, 0, 1];
      nv.scene.crosshairPos = [0.5, 0.5, 0.5];
      if ("volScaleMultiplier" in nv) nv.volScaleMultiplier = 1;   // also clear any 3D-render zoom
      nv.updateGLVolume();
      nv.drawScene();
    } catch (_) { /* best-effort recentre */ }
  }
}


// Apply the chosen error-overlay colormap. The error is always windowed on |error| (magnitude) with a
// transparency floor: cal_min hides near-zero background, cal_max saturates, both mirrored to the
// negative side. χ error uses the eval's ppm scale (floor 0.01, sat 0.1 ppm).
function setErrorColormap() {
  if (!activeErrVol) return;
  const ov = activeErrVol;
  const cfg = ERROR_CMAPS[errorCtl.cmapSelect.value] || ERROR_CMAPS.diverging;
  ov.colormap = cfg.colormap;
  ov.colormapNegative = cfg.colormapNegative;
  // Window on |error|, mirrored to both signs so zero is a fixed, transparent centre. cal_min = inner
  // (transparency floor: errors below it, including exact zero, don't render); cal_max = outer
  // (saturation: beyond it everything shows the top colour). Moving either changes only the ±inner/
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
  [allRuns, algos, registry, datasetsReg] = await Promise.all([loadRuns(), loadAlgos(), loadRegistry(), loadDatasets()]);
  await ensureReproJson();   // eager so an in-silico pipeline can offer its harmonization analog
  const q = new URLSearchParams(location.search);
  // Shared control handlers (used by every dataset, harmonization included).
  $("run-filter").addEventListener("input", (e) => { filter = e.target.value; buildSidebar(); });
  $("metrics-tabs").querySelectorAll("[data-mtab]").forEach((b) =>
    b.addEventListener("click", () => { metricsTab = b.dataset.mtab; renderMetricsPanel(); }));
  document.querySelectorAll("#nav-toggle button").forEach((b) => b.addEventListener("click", () => { navMode = b.dataset.mode; buildSidebar(); }));
  document.querySelectorAll("#domain-toggle button").forEach((b) => b.addEventListener("click", () => browseDataset(b.dataset.domain)));

  // Harmonization entry: ?pipeline=<id>&dataset=repro&acq=<acquisition>. Generate the acquisition's
  // pipeline pool (see ensureReproRuns) and open the requested pipeline. From here it's the same
  // Pipelines machinery as in-silico.
  if (q.get("pipeline") && q.get("dataset") === "repro") {
    reproPipe = q.get("pipeline");
    reproAcq = acqExists(q.get("acq")) ? q.get("acq") : "cima-bridge-run1";
    ensureReproRuns(reproAcq);
    domain = "repro"; navMode = "pipelines"; reproMode = true;
    run = allRuns.find((r) => r.id === reproRunId(reproPipe, reproAcq)) || composedRuns()[0];
    if (!run) { $("sub-title").textContent = "No harmonization results yet"; return; }
    buildSidebar();
    await loadRun();
    return;
  }

  // Accept ?run=<run-id> (e.g. ismv-iso), or a bare slug via ?run= / ?method= (e.g. ?method=ismv,
  // the form Zenodo records link to) → resolve to that algorithm's isolated run.
  const want = q.get("run") || q.get("method");
  run = allRuns.find((r) => r.id === want)
    || allRuns.find((r) => r.mode === "isolated" && r.slug === want)
    || allRuns.find((r) => r.status !== "DNF") || allRuns[0];
  if (!run) { $("sub-title").textContent = "No runs"; return; }
  domain = datasetOf(run);
  navMode = run.mode === "composed" ? "pipelines" : "stages";
  // Deep links: ?layer=truth selects the ground-truth base; ?layer=error (or ?error=1) turns on the
  // error overlay. Applied before the first render so loadRun picks them up.
  const layer = q.get("layer");
  if (layer === "truth") curBase = "truth";
  if (layer === "error" || q.get("error") === "1") showError = true;
  // ?mtab=regions|error deep-links a Metrics-card tab. The tab stays remembered through the initial
  // (pre-regions) render and activates once loadRun fetches THIS run's per-region file (see loadRun);
  // renderMetricsPanel falls back to the metric table meanwhile.
  if (["regions", "error"].includes(q.get("mtab"))) metricsTab = q.get("mtab");
  buildSidebar();
  await loadRun();
}
init();
