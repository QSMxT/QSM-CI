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
  nrmse:           { label: "NRMSE",            unit: "%", better: "lower",  dp: 1,
    desc: "Normalized root-mean-square error within the mask, after demeaning both maps. 0 = perfect; ~100% ≈ a flat map (the do-nothing baseline)." },
  nrmse_detrend:   { label: "Detrended NRMSE",  unit: "%", better: "lower",  dp: 1,
    desc: "NRMSE after correcting a global linear scaling of the reconstruction — measures error independent of overall contrast/gain." },
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
  runtime_s:       { label: "Runtime",          unit: "s", better: "lower",  dp: 1,
    desc: "Wall-clock time taken by this run." },
};
const PREFERRED = ["nrmse", "nrmse_detrend", "nrmse_tissue", "nrmse_blood", "nrmse_dgm",
  "dgm_linearity", "calc_moment_dev", "calc_streak", "correlation", "xsim"];

const STAGE_LABEL = {
  "field-mapping": "Field mapping",
  bfr: "Background removal",
  dipole: "Dipole inversion",
  "bfr+dipole": "Background removal + dipole inversion",
  "unwrap+bfr": "Unwrapping + background removal",
  "end-to-end": "End-to-end",
};
const MEDALS = ["🥇", "🥈", "🥉"];

async function loadRuns() {
  const res = await fetch("results/index.json", { cache: "no-store" });
  return (await res.json()).runs || [];
}

async function loadAlgos() {
  try {
    const res = await fetch("algorithms.json", { cache: "no-store" });
    return (await res.json()).algorithms || [];
  } catch (e) { return []; }
}

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
// Muted red → gold → sage for t in [0,1] (0 = worst, 1 = best) — the combination-matrix heat scale.
function heatScale(t) {
  const stops = [[190, 107, 107], [196, 158, 96], [110, 168, 134]];
  const x = Math.max(0, Math.min(1, t)) * 2, i = Math.min(1, Math.floor(x)), f = x - i;
  const c = stops[i].map((a, k) => Math.round(a + (stops[i + 1][k] - a) * f));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

function fmt(v, key) {
  if (v == null) return "—";
  const m = METRICS[key] || { dp: 2, unit: "" };
  return Number(v).toFixed(m.dp) + (m.unit || "");
}

// Column keys present (non-null) in a set of runs, in preferred order (+ runtime).
function metricCols(runs) {
  const present = new Set();
  runs.forEach((r) => Object.entries(r.metrics || {}).forEach(([k, v]) => v != null && present.add(k)));
  const cols = PREFERRED.filter((k) => present.has(k));
  if (runs.some((r) => r.runtime_s != null)) cols.push("runtime_s");
  return cols;
}

// Red→green background for a value within [lo,hi], respecting metric direction.
function heatColor(v, lo, hi, key) {
  if (v == null) return "transparent";
  let t = hi === lo ? 0.5 : (v - lo) / (hi - lo);
  if ((METRICS[key]?.better || "higher") === "lower") t = 1 - t;
  const hue = Math.round(t * 130);         // 0 red → 130 green
  return `hsl(${hue} 72% 46%)`;
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
    nav.innerHTML = `
      <div class="mx-auto max-w-6xl px-6 h-16 flex items-center justify-between">
        <a href="index.html" class="flex items-center gap-2.5">
          <svg width="26" height="26" viewBox="0 0 32 32" fill="none" aria-hidden="true">
            <defs><linearGradient id="ci-nav-g" x1="2" y1="2" x2="30" y2="30" gradientUnits="userSpaceOnUse">
              <stop stop-color="#34d399"/><stop offset="1" stop-color="#059669"/></linearGradient></defs>
            <rect x="1.5" y="1.5" width="29" height="29" rx="8" fill="url(#ci-nav-g)"/>
            <g transform="translate(4,4)" stroke="#fff" stroke-width="2.6" stroke-linecap="round">
              <path d="M6 19v-4"/><path d="M12 19V9"/><path d="M18 19V5"/></g>
          </svg>
          <span class="font-semibold text-gray-900 dark:text-gray-100 tracking-tight">QSM-CI</span>
        </a>
        <div class="flex items-center gap-6">
          ${navLink("index.html", "Home", page === "index.html")}
          ${navLink("leaderboard.html", "Leaderboard", page === "leaderboard.html")}
          ${navLink("running.html", "Run", page === "running.html")}
          ${navLink("submit.html", "Submit", page === "submit.html")}
          <button onclick="toggleTheme()" class="text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors" title="Toggle theme">${isDark ? SUN : MOON}</button>
          <a href="${GH}" class="text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors" title="GitHub">
            <svg width="20" height="20" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
          </a>
        </div>
      </div>`;
  }
  const footer = document.getElementById("site-footer");
  if (footer) {
    footer.className = "border-t border-gray-200 mt-20 dark:border-gray-800";
    footer.innerHTML = `
      <div class="mx-auto max-w-6xl px-6 py-10 text-sm text-gray-500 dark:text-gray-400 flex flex-col sm:flex-row justify-between gap-4">
        <p>QSM-CI — a challenge for Quantitative Susceptibility Mapping reconstruction.</p>
        <p>Scored with <a href="${GH}/tree/main/eval" class="text-emerald-600 hover:underline">qsm-eval</a>
           · metrics from <a href="https://github.com/astewartau/QSM.rs" class="text-emerald-600 hover:underline">QSM.rs</a></p>
      </div>`;
  }
}

document.addEventListener("DOMContentLoaded", injectChrome);

// Exposed for module scripts (e.g. the NiiVue viewer, which must be a module for `import`).
window.QSM = { GH, METRICS, STAGE_LABEL, MEDALS, loadRuns, loadAlgos, loadRegistry, doiFor, val, fmt, metricCols, heatColor, robustRange, heatScale };
