// Shared chrome (nav + footer) and helpers for the QSM-CI site.
// Loaded before Alpine so the page component factories can use these globals.

// Cross-project "ecosystem bar" shared across all QSM sites (see QSMxT/qsmxt.github.io).
(function () {
  const s = document.createElement("script");
  const local = location.hostname === "localhost" || location.hostname === "127.0.0.1";
  s.src = local ? "/qsm-nav.js" : "https://qsmxt.github.io/qsm-nav.js";
  s.dataset.current = "ci";
  document.head.appendChild(s);
})();

const GH = "https://github.com/QSMxT/QSM-CI";

// ---- theme (dark mode) ------------------------------------------------------
function applyTheme() {
  const saved = localStorage.getItem("qsmci-theme");
  // Dark-first across the QSM family: default to dark unless the user chose light.
  const dark = saved ? saved === "dark" : true;
  document.documentElement.classList.toggle("dark", dark);
}
function toggleTheme() {
  const dark = !document.documentElement.classList.contains("dark");
  localStorage.setItem("qsmci-theme", dark ? "dark" : "light");
  document.documentElement.classList.toggle("dark", dark);
  injectChrome();
}
applyTheme();  // run immediately (app.js loads in <head>) to avoid a flash

// Mobile nav dropdown toggle (hamburger). The links collapse below md; this shows/hides them.
function toggleNav() {
  const m = document.getElementById("nav-mobile");
  if (m) m.classList.toggle("hidden");
}

const SUN = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
const MOON = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/></svg>';

// Dark-mode colour layer, scoped to <main>, so page content picks up dark styling without a
// dark: variant on every element (nav/footer are themed in injectChrome; submission page also
// uses explicit dark: variants with matching colours).
(function injectThemeCSS() {
  const css = `
  /* base form control styling (Tailwind CDN has no forms plugin) */
  main input:not([type=checkbox]):not([type=radio]):not([type=range]),main select,main textarea{
    padding:.5rem .75rem;border:1px solid #d1d5db;border-radius:.5rem;font-size:.875rem;line-height:1.25rem;background-color:#fff;transition:border-color .12s,box-shadow .12s}
  main input:not([type=checkbox]):not([type=radio]):not([type=range]):focus,main select:focus,main textarea:focus{
    outline:none;border-color:#10b981;box-shadow:0 0 0 3px rgba(16,185,129,.22)}
  main select{padding-right:2rem;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='none' stroke='%239ca3af' stroke-width='2'%3E%3Cpath d='M4 6l4 4 4-4'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right .6rem center;-webkit-appearance:none;appearance:none}
  main ::placeholder{color:#9ca3af}
  html.dark main input:not([type=checkbox]):not([type=radio]):not([type=range]),html.dark main select,html.dark main textarea{background-color:#1f2937;border-color:#374151;color:#f3f4f6}
  html.dark main ::placeholder{color:#6b7280}
  html.dark main .bg-white{background-color:#111827}
  html.dark main .bg-gray-50{background-color:#1f2937}
  html.dark main .bg-gray-100{background-color:#1f2937}
  html.dark main .border-gray-200,html.dark main .border-gray-100{border-color:#1f2937}
  html.dark main .border-gray-300{border-color:#374151}
  html.dark main .divide-gray-100>:not([hidden])~:not([hidden]),html.dark main .divide-gray-800>:not([hidden])~:not([hidden]){border-color:#1f2937}
  html.dark main .bg-emerald-50{background-color:rgba(16,185,129,.13)}
  html.dark main .text-emerald-700{color:#6ee7b7}
  html.dark main .text-emerald-600{color:#34d399}
  html.dark main .ring-emerald-100{--tw-ring-color:rgba(16,185,129,.25)}
  html.dark main .hover\\:bg-emerald-100:hover{background-color:rgba(16,185,129,.2)}
  html.dark main .text-gray-900{color:#f3f4f6}
  html.dark main .text-gray-700{color:#d1d5db}
  html.dark main .text-gray-600,html.dark main .text-gray-500{color:#9ca3af}
  html.dark main .text-gray-400{color:#6b7280}
  html.dark main .text-gray-300{color:#4b5563}
  html.dark main .hover\\:bg-gray-50:hover{background-color:#1f2937}
  html.dark main .hover\\:bg-emerald-50\\/40:hover,html.dark main .hover\\:bg-emerald-50:hover{background-color:rgba(16,185,129,.1)}
  html.dark main .group:hover .group-hover\\:bg-emerald-50\\/40{background-color:rgba(16,185,129,.1)}
  html.dark main .bg-gray-50\\/70{background-color:#0f172a}
  html.dark main input,html.dark main select{background-color:#1f2937;border-color:#374151;color:#f3f4f6}
  html.dark main .ring-gray-200,html.dark main .ring-gray-300{--tw-ring-color:#374151}
  html.dark main .shadow-sm{box-shadow:0 1px 2px 0 rgba(0,0,0,.4)}
  html.dark .from-emerald-50\\/70{--tw-gradient-from:rgba(2,44,34,.4) var(--tw-gradient-from-position)}`;
  const s = document.createElement("style");
  s.textContent = css;
  document.addEventListener("DOMContentLoaded", () => document.head.appendChild(s));
})();

// Global hover tooltip: any element with a [data-tip] attribute shows a styled tooltip. Rendered in a
// single body-level layer (position:fixed) so it never clips inside overflow/scroll containers such as
// the leaderboard table. Add `has-tip` for the dotted-underline "hover me" affordance.
(function tooltips() {
  const css = `
  .has-tip{cursor:help;border-bottom:1px dotted rgba(107,114,128,.55)}
  .qsm-tip{position:fixed;z-index:9999;max-width:270px;background:#111827;color:#f3f4f6;font-size:11px;
    font-weight:400;line-height:1.5;letter-spacing:normal;text-transform:none;text-align:left;
    padding:8px 10px;border-radius:8px;box-shadow:0 10px 30px rgba(0,0,0,.35);pointer-events:none;
    opacity:0;transition:opacity .12s;display:none}
  .qsm-tip.show{opacity:1}
  html.dark .qsm-tip{background:#0b1220;box-shadow:0 10px 30px rgba(0,0,0,.6);outline:1px solid rgba(148,163,184,.15)}`;
  let tip = null, cur = null;
  // Follow the cursor: offset below-right, flipping to the other side near a viewport edge.
  const positionAt = (x, y) => {
    if (!tip) return;
    const tw = tip.offsetWidth, th = tip.offsetHeight, pad = 8, off = 16;
    let left = x + off, top = y + off;
    if (left + tw > window.innerWidth - pad) left = x - tw - off;
    if (top + th > window.innerHeight - pad) top = y - th - off;
    tip.style.left = Math.max(pad, left) + "px";
    tip.style.top = Math.max(pad, top) + "px";
  };
  const show = (target, x, y) => {
    const text = target.getAttribute("data-tip"); if (!text) return;
    cur = target;
    if (!tip) { tip = document.createElement("div"); tip.className = "qsm-tip"; document.body.appendChild(tip); }
    tip.textContent = text; tip.style.display = "block";
    positionAt(x, y); tip.classList.add("show");
  };
  const hide = () => { cur = null; if (tip) { tip.classList.remove("show"); tip.style.display = "none"; } };
  document.addEventListener("mouseover", (e) => { const t = e.target.closest?.("[data-tip]"); if (t) show(t, e.clientX, e.clientY); });
  document.addEventListener("mousemove", (e) => {
    if (!cur) return;
    if (e.target.closest?.("[data-tip]") === cur) positionAt(e.clientX, e.clientY); else hide();
  });
  document.addEventListener("mouseout", (e) => { const t = e.target.closest?.("[data-tip]"); if (t === cur && !t?.contains(e.relatedTarget)) hide(); });
  document.addEventListener("mousedown", hide, true);
  const s = document.createElement("style"); s.textContent = css;
  document.addEventListener("DOMContentLoaded", () => document.head.appendChild(s));
})();

// Metric metadata: label, unit, better direction, decimals, and a plain-language description
// (surfaced as hover tooltips). Descriptions mirror eval/qsm_eval.py (ported from QSM.rs).
const METRICS = {
  mspe:            { label: "MSPE",             unit: "%", better: "lower",  dp: 1,
    desc: "Mean squared percentage error of ROI means (Ridani et al., MRM 2026): a per-region quantification-bias metric, comparable to the paper's published χ-separation numbers." },
  mev:             { label: "MEV",              unit: "%", better: "lower",  dp: 1,
    desc: "Maximum error variation (Ridani et al. 2026, Fig 5): the fractional drop in χ− error from fibres parallel to B0 to perpendicular. High = strongly orientation-dependent error; a diagnostic, not a ranking metric." },
  nrmse:           { label: "NRMSE",            unit: "%", better: "lower",  dp: 1,
    desc: "Normalized root-mean-square error within the mask, after demeaning both maps. 0 = perfect; ~100% ≈ a flat map (the do-nothing baseline)." },
  nrmse_detrend:   { label: "Detrended NRMSE",  unit: "%", better: "lower",  dp: 1,
    desc: "NRMSE after correcting a global linear scaling of the reconstruction: measures error independent of overall contrast/gain." },
  nrmse_tissue:    { label: "Tissue NRMSE",     unit: "%", better: "lower",  dp: 1,
    desc: "Demeaned NRMSE restricted to brain-tissue regions (grey + white matter)." },
  nrmse_blood:     { label: "Blood NRMSE",      unit: "%", better: "lower",  dp: 1,
    desc: "Demeaned NRMSE restricted to venous blood regions." },
  nrmse_dgm:       { label: "DGM NRMSE",        unit: "%", better: "lower",  dp: 1,
    desc: "Demeaned NRMSE restricted to the deep grey-matter nuclei." },
  dgm_linearity:   { label: "DGM linearity",    unit: "",  better: "lower",  dp: 3,
    desc: "|1 − slope| of mean reconstructed vs. true susceptibility across the six deep grey-matter nuclei. 0 = a perfectly linear response." },
  calc_moment_dev: { label: "Calcification dev.",unit: "", better: "lower",  dp: 2,
    desc: "Absolute error in the total susceptibility moment recovered inside the calcification." },
  calc_streak:     { label: "Streak",           unit: "",  better: "lower",  dp: 3,
    desc: "Streaking-artefact level around the calcification: residual spread near its rim, relative to the calcification's mean susceptibility." },
  correlation:     { label: "Correlation",      unit: "",  better: "higher", dp: 3,
    desc: "Pearson correlation between reconstructed and ground-truth χ within the mask. 1 = perfect." },
  xsim:            { label: "XSIM",             unit: "",  better: "higher", dp: 3,
    desc: "Structural-similarity index tuned for QSM (5×5×5 windows). 1 = identical to the ground truth." },
  hfen:            { label: "HFEN",             unit: "%", better: "lower",  dp: 1,
    desc: "High-Frequency Error Norm (%): error in a Laplacian-of-Gaussian high-pass of the map, i.e. how well fine edges/detail are recovered relative to the ground truth. 0 = perfect. The classic 2016 QSM Reconstruction Challenge fine-detail metric." },
  para_leak:       { label: "χ−→χ+ leak",       unit: "",  better: "lower",  dp: 3,
    desc: "Whole-brain regression slope of χ+ on the χ− ground truth: the fraction of diamagnetic signal bleeding into the paramagnetic map. 0 = clean; magnitude = contamination. Unlike xSIM it isn't fooled by the shared R2' common mode." },
  dia_leak:        { label: "χ+→χ− leak",       unit: "",  better: "lower",  dp: 3,
    desc: "Whole-brain regression slope of χ− on the χ+ ground truth: the fraction of paramagnetic signal bleeding into the diamagnetic map. 0 = clean; magnitude = contamination. Unlike xSIM it isn't fooled by the shared R2' common mode." },
  runtime_s:       { label: "Runtime",          unit: "s", better: "lower",  dp: 1,
    desc: "Wall-clock time to produce this output; for a combined pipeline, the sum of its field-mapping, background-removal and dipole-inversion stages. Measured on GitHub-hosted runners (≈4 vCPU, 16 GB RAM, no GPU, so learning-based methods run on CPU); treat it as relative speed, not an absolute benchmark." },
  mem_peak_bytes:  { label: "Peak memory",       unit: "",  better: "lower",  dp: 0,
    desc: "Peak resident memory (max RSS) sampled once per second while the method runs — the RAM it needs to fit on a machine. Measured on the CI runners; treat it as relative, not an absolute benchmark." },
  cpu_cores_avg:   { label: "Avg CPU",           unit: " cores", better: "higher", dp: 1,
    desc: "Average CPU cores busy over the run (CPU-time ÷ wall-time): how well the method parallelises. ~1 = single-threaded, higher = more cores used at once. A utilisation indicator, not a quality score; measured on the CI runners." },
};
// Metric column order for tables: the METRICS declaration order minus the top-level resource fields
// (runtime / peak memory / avg CPU), which metricCols() appends as trailing columns in that order.
const RESOURCE_COLS = ["runtime_s", "mem_peak_bytes", "cpu_cores_avg"];
const PREFERRED = Object.keys(METRICS).filter((k) => !RESOURCE_COLS.includes(k));

const STAGE_LABEL = {
  "field-mapping": "Field mapping",
  bfr: "Background removal",
  dipole: "Dipole inversion",
  "bfr+dipole": "Background removal + dipole inversion",
  "unwrap+bfr": "Unwrapping + background removal",
  "end-to-end": "End-to-end",
  "chi-separation": "Source separation",
  "r2prime-generation": "R2′ estimation",
};
const MEDALS = ["🥇", "🥈", "🥉"];

async function loadRuns() {
  const res = await fetch("results/index.json", { cache: "no-store" });
  return (await res.json()).runs || [];
}

// algorithms.json bundles the method manifest AND the dataset/phantom registry (a `datasets` block
// mirroring scripts/datasets.json) — fetch it once and serve both from the same promise.
let _algoManifest = null;
async function loadAlgoManifest() {
  if (_algoManifest) return _algoManifest;
  _algoManifest = (async () => {
    try {
      const res = await fetch("algorithms.json", { cache: "no-store" });
      return await res.json();
    } catch (e) { return {}; }
  })();
  return _algoManifest;
}
async function loadAlgos() { return (await loadAlgoManifest()).algorithms || []; }
// Phantom registry: { <phantom-id>: { track, label, default, … } }. A run row's `phantom` field is
// one of these keys; a row WITHOUT the field was scored on its track's default phantom.
async function loadDatasets() { return (await loadAlgoManifest()).datasets || {}; }

// The Zenodo method registry (qsm_ci/registry.json), served alongside the site. Maps a method slug
// to its concept DOI + published versions, so pages can show a citable DOI per method.
let _registry = null;
async function loadRegistry() {
  if (_registry) return _registry;
  try {
    const res = await fetch("registry.json", { cache: "no-store" });
    _registry = res.ok ? await res.json() : {};
  } catch (e) { _registry = {}; }
  return _registry;
}
// Per-region descriptive stats for ONE run: { chi|para|dia: { labels: {id: name},
// recon: {id: {n, mean, std, median}}, truth: {…} } }. Stored per-run (results/<id>/regions.json),
// published to Hugging Face with the run's volumes and referenced by `run.regions_url` — exactly
// like resources.json/resources_url — so the all-runs regional data never bloats the committed
// index or git. Falls back to the local path for `python -m http.server` dev (the file is on disk
// after a local score/backfill, before it's published). Cached per run id; null when unavailable.
const _runRegions = new Map();
async function loadRunRegions(run) {
  if (!run || !run.id) return null;
  if (_runRegions.has(run.id)) return _runRegions.get(run.id);
  const url = run.regions_url || `results/${run.id}/regions.json`;
  const entry = await fetch(url, { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : null)).catch(() => null);
  _runRegions.set(run.id, entry);
  return entry;
}

// { concept_doi, version_doi, version, url } for a slug, or null if unpublished.
function doiFor(registry, slug) {
  const e = registry && registry[slug];
  if (!e || !e.concept_doi) return null;
  const v = (e.versions && e.versions[e.latest]) || {};
  return { concept_doi: e.concept_doi, version_doi: v.version_doi || null,
           version: e.latest || null, url: "https://doi.org/" + e.concept_doi };
}

function val(run, key) { return run.metrics?.[key] ?? run[key]; }

// Robust [lo,hi] colour-scale window via Tukey fences: a few extreme outliers saturate at the ends
// instead of crushing everyone else into one colour. Shared by the leaderboard matrix and the
// submission-page metric ranks so their colouring matches. Falls back to min/max when too few points.
function robustRange(vals) {
  const s = vals.filter((v) => v != null && isFinite(v)).sort((a, b) => a - b);
  const n = s.length;
  if (n < 4) return [s[0] ?? 0, s[n - 1] ?? 1];
  const q = (p) => s[Math.min(n - 1, Math.max(0, Math.round(p * (n - 1))))];
  const q1 = q(0.25), q3 = q(0.75), iqr = q3 - q1;
  const lo = Math.max(s[0], q1 - 1.5 * iqr), hi = Math.min(s[n - 1], q3 + 1.5 * iqr);
  return lo < hi ? [lo, hi] : [s[0], s[n - 1]];
}
// Muted red → gold → sage for t in [0,1] (0 = worst, 1 = best): the combination-matrix heat scale.
function heatScale(t) {
  const stops = [[190, 107, 107], [196, 158, 96], [110, 168, 134]];
  const x = Math.max(0, Math.min(1, t)) * 2, i = Math.min(1, Math.floor(x)), f = x - i;
  const c = stops[i].map((a, k) => Math.round(a + (stops[i + 1][k] - a) * f));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

// Humanised duration: 3s · 1m 2s · 1h 4m 2s (matches the runtime style used across the leaderboard).
function fmtDuration(v) {
  if (v == null || !isFinite(v)) return "—";
  const s = Math.round(v);
  if (s < 60) return s + "s";
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return h ? `${h}h ${m}m ${sec}s` : `${m}m ${sec}s`;
}

// Humanised byte size for peak-memory cells: 986 MB · 1.2 GB · 14 GB (1 dp under 10 GB, else 0).
function fmtBytes(v) {
  if (v == null || !isFinite(v)) return "—";
  return v >= 1e9 ? (v / 1e9).toFixed(v >= 1e10 ? 0 : 1) + " GB" : Math.round(v / 1e6) + " MB";
}

function fmt(v, key) {
  if (v == null) return "—";
  if (key === "runtime_s") return fmtDuration(v);
  if (key === "mem_peak_bytes") return fmtBytes(v);
  const m = METRICS[key] || { dp: 2, unit: "" };
  return Number(v).toFixed(m.dp) + (m.unit || "");
}

// Column keys present (non-null) in a set of runs, in preferred order (+ runtime).
function metricCols(runs) {
  const present = new Set();
  runs.forEach((r) => Object.entries(r.metrics || {}).forEach(([k, v]) => v != null && present.add(k)));
  const cols = PREFERRED.filter((k) => present.has(k));
  // Resource fields live at the top level (not under .metrics); append any that are present, in order.
  RESOURCE_COLS.forEach((k) => { if (runs.some((r) => r[k] != null)) cols.push(k); });
  return cols;
}

// ---- shared chrome ----------------------------------------------------------

function navLink(href, label, active) {
  const cls = active
    ? "text-emerald-600 dark:text-emerald-400 font-semibold"
    : "text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100";
  return `<a href="${href}" class="text-sm ${cls} transition-colors">${label}</a>`;
}

function injectChrome() {
  const page = location.pathname.split("/").pop() || "index.html";
  const nav = document.getElementById("site-nav");
  if (nav) {
    nav.className = "sticky top-0 z-30 backdrop-blur bg-white/80 border-b border-gray-200 dark:bg-gray-950/80 dark:border-gray-800";
    const isDark = document.documentElement.classList.contains("dark");
    const GHLINK = `<a href="${GH}" class="text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors" title="GitHub">
            <svg width="20" height="20" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
          </a>`;
    const links = [["index.html","Home"],["results.html","Results"],["running.html","Run"],["submit.html","Submit"]];
    nav.innerHTML = `
      <div class="mx-auto max-w-6xl px-6 h-16 flex items-center justify-between gap-3">
        <a href="index.html" class="flex shrink-0 items-center gap-2.5">
          <svg width="26" height="26" viewBox="0 0 32 32" fill="none" aria-hidden="true" class="shrink-0">
            <defs><linearGradient id="ci-nav-g" x1="2" y1="2" x2="30" y2="30" gradientUnits="userSpaceOnUse">
              <stop stop-color="#34d399"/><stop offset="1" stop-color="#059669"/></linearGradient></defs>
            <rect x="1.5" y="1.5" width="29" height="29" rx="8" fill="url(#ci-nav-g)"/>
            <g transform="translate(4,4)" stroke="#fff" stroke-width="2.6" stroke-linecap="round">
              <path d="M6 19v-4"/><path d="M12 19V9"/><path d="M18 19V5"/></g>
          </svg>
          <span class="font-semibold text-gray-900 dark:text-gray-100 tracking-tight whitespace-nowrap">QSM-CI</span>
        </a>
        <div class="flex items-center gap-6">
          <div class="hidden items-center gap-6 md:flex">
            ${links.map(([h,l]) => navLink(h, l, page === h)).join("")}
          </div>
          <button onclick="toggleTheme()" class="text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors" title="Toggle theme">${isDark ? SUN : MOON}</button>
          ${GHLINK}
          <button onclick="toggleNav()" class="text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100 transition-colors md:hidden" title="Menu" aria-label="Menu">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
          </button>
        </div>
      </div>
      <div id="nav-mobile" class="hidden border-t border-gray-200 px-6 py-2 dark:border-gray-800 md:hidden">
        ${links.map(([h,l]) => `<a href="${h}" class="block rounded-lg px-2 py-2.5 text-sm ${page===h ? "font-semibold text-emerald-600 dark:text-emerald-400" : "text-gray-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-900"}">${l}</a>`).join("")}
      </div>`;
  }
  const footer = document.getElementById("site-footer");
  if (footer) {
    footer.className = "border-t border-gray-200 mt-20 dark:border-gray-800";
    footer.innerHTML = `
      <div class="mx-auto max-w-6xl px-6 py-10 text-sm text-gray-500 dark:text-gray-400 flex flex-col sm:flex-row justify-between gap-4">
        <p>QSM-CI: a benchmarking platform for Quantitative Susceptibility Mapping.</p>
        <p><a href="${GH}" class="text-emerald-600 hover:underline">github.com/QSMxT/QSM-CI</a></p>
      </div>`;
  }
}

document.addEventListener("DOMContentLoaded", injectChrome);

// Exposed for module scripts (e.g. the NiiVue viewer, which must be a module for `import`).
window.QSM = { GH, METRICS, STAGE_LABEL, MEDALS, loadRuns, loadAlgos, loadDatasets, loadRegistry, loadRunRegions, doiFor, val, fmt, fmtDuration, fmtBytes, metricCols, robustRange, heatScale };
