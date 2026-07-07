// Shared chrome (nav + footer) and helpers for the QSM-CI site.
// Loaded before Alpine so the page component factories can use these globals.

const GH = "https://github.com/astewartau/qsm-ci";

// Metric metadata: label, unit, better direction, decimals.
const METRICS = {
  nrmse:           { label: "NRMSE",            unit: "%", better: "lower",  dp: 1 },
  nrmse_detrend:   { label: "Detrended NRMSE",  unit: "%", better: "lower",  dp: 1 },
  nrmse_tissue:    { label: "Tissue NRMSE",     unit: "%", better: "lower",  dp: 1 },
  nrmse_blood:     { label: "Blood NRMSE",      unit: "%", better: "lower",  dp: 1 },
  nrmse_dgm:       { label: "DGM NRMSE",        unit: "%", better: "lower",  dp: 1 },
  dgm_linearity:   { label: "DGM linearity",    unit: "",  better: "lower",  dp: 3 },
  calc_moment_dev: { label: "Calcification dev.",unit: "", better: "lower",  dp: 2 },
  calc_streak:     { label: "Streak",           unit: "",  better: "lower",  dp: 3 },
  correlation:     { label: "Correlation",      unit: "",  better: "higher", dp: 3 },
  xsim:            { label: "XSIM",             unit: "",  better: "higher", dp: 3 },
  runtime_s:       { label: "Runtime",          unit: "s", better: "lower",  dp: 1 },
};
const PREFERRED = ["nrmse", "nrmse_detrend", "nrmse_tissue", "nrmse_blood", "nrmse_dgm",
  "dgm_linearity", "calc_moment_dev", "calc_streak", "correlation", "xsim"];

const STAGE_LABEL = {
  "field-mapping": "Field mapping",
  bfr: "Background removal",
  dipole: "Dipole inversion",
};
const MEDALS = ["🥇", "🥈", "🥉"];

async function loadRuns() {
  const res = await fetch("results/index.json", { cache: "no-store" });
  return (await res.json()).runs || [];
}

function val(run, key) { return run.metrics?.[key] ?? run[key]; }

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
    ? "text-indigo-600 font-semibold"
    : "text-gray-600 hover:text-gray-900";
  return `<a href="${href}" class="text-sm ${cls} transition-colors">${label}</a>`;
}

function injectChrome() {
  const page = location.pathname.split("/").pop() || "index.html";
  const nav = document.getElementById("site-nav");
  if (nav) {
    nav.className = "sticky top-0 z-30 backdrop-blur bg-white/80 border-b border-gray-200";
    nav.innerHTML = `
      <div class="mx-auto max-w-6xl px-6 h-16 flex items-center justify-between">
        <a href="index.html" class="flex items-center gap-2.5">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" class="text-indigo-600">
            <path d="M12 2l8.66 5v10L12 22l-8.66-5V7L12 2z" fill="currentColor" fill-opacity="0.12"/>
            <path d="M12 2l8.66 5v10L12 22l-8.66-5V7L12 2z" stroke="currentColor" stroke-width="1.6"/>
            <circle cx="12" cy="12" r="3" fill="currentColor"/>
          </svg>
          <span class="font-semibold text-gray-900 tracking-tight">QSM-CI</span>
        </a>
        <div class="flex items-center gap-6">
          ${navLink("index.html", "Home", page === "index.html")}
          ${navLink("leaderboard.html", "Leaderboard", page === "leaderboard.html")}
          ${navLink(GH + "/blob/main/docs/submitting.md", "Submit", false)}
          <a href="${GH}" class="text-gray-400 hover:text-gray-900 transition-colors" title="GitHub">
            <svg width="20" height="20" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
          </a>
        </div>
      </div>`;
  }
  const footer = document.getElementById("site-footer");
  if (footer) {
    footer.className = "border-t border-gray-200 mt-20";
    footer.innerHTML = `
      <div class="mx-auto max-w-6xl px-6 py-10 text-sm text-gray-500 flex flex-col sm:flex-row justify-between gap-4">
        <p>QSM-CI — a challenge for Quantitative Susceptibility Mapping reconstruction.</p>
        <p>Scored with <a href="${GH}/tree/main/eval" class="text-indigo-600 hover:underline">qsm-eval</a>
           · metrics from <a href="https://github.com/astewartau/QSM.rs" class="text-indigo-600 hover:underline">QSM.rs</a></p>
      </div>`;
  }
}

document.addEventListener("DOMContentLoaded", injectChrome);

// Exposed for module scripts (e.g. the NiiVue viewer, which must be a module for `import`).
window.QSM = { GH, METRICS, STAGE_LABEL, MEDALS, loadRuns, val, fmt, metricCols, heatColor };
