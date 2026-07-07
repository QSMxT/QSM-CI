// Per-submission detail page + NiiVue viewer.
// Mirrors the qsmbly integration (~/repos/qsm/qsmbly/qsmbly): NiiVue from CDN, attach to a
// canvas, multiplanar view, load volumes from static URLs, add an overlay with colormap + opacity.

import { Niivue } from "https://unpkg.com/@niivue/niivue@0.57.0/dist/index.js";

// Same viewer config qsmbly uses (js/app/config.js VIEWER_CONFIG).
const VIEWER_CONFIG = {
  loadingText: "loading…",
  dragToMeasure: false,
  isColorbar: true,
  textHeight: 0.03,
  show3Dcrosshair: false,
  crosshairWidth: 0.75,
};

const METRIC_ROWS = [
  ["nrmse", "NRMSE (demeaned) %", 2],
  ["nrmse_detrend", "NRMSE (detrended) %", 2],
  ["nrmse_tissue", "NRMSE tissue (GM/WM/Thal) %", 2],
  ["nrmse_blood", "NRMSE blood %", 2],
  ["nrmse_dgm", "NRMSE deep gray matter %", 2],
  ["dgm_linearity", "DGM linearity |1−slope|", 4],
  ["calc_moment_dev", "Calcification moment dev.", 4],
  ["calc_streak", "Streak artifact", 4],
  ["correlation", "Correlation r", 4],
  ["xsim", "XSIM", 4],
  ["runtime_s", "Runtime (s)", 2],
];

const runId = new URLSearchParams(location.search).get("run");

let nv;
let run;      // the run's index.json entry
let baseUrl;  // results/<slug>/<track>/ — where recon/truth/error nii.gz live

async function init() {
  const index = await (await fetch("results/index.json")).json();
  run = (index.runs || []).find((r) => r.id === runId);
  if (!run) { document.getElementById("title").textContent = "Run not found"; return; }

  document.getElementById("title").textContent = run.name;
  document.getElementById("meta").innerHTML =
    `${(run.authors || []).join(", ")} · track: ${run.track} · ` +
    `image <code>${run.image || "—"}</code>`;

  renderMetrics();

  baseUrl = `results/${run.slug}/${run.track}/`;
  nv = new Niivue({
    ...VIEWER_CONFIG,
    onLocationChange: (d) => { document.getElementById("intensity").innerHTML = d.string; },
  });
  await nv.attachTo("gl1");
  nv.setSliceType(nv.sliceTypeMultiplanar);
  try {
    await showLayer("recon");
  } catch (e) {
    document.querySelector(".viewer-section").innerHTML =
      `<p class="empty">Interactive volumes not published for this run yet. ` +
      `Enable volume export in the evaluation step to view reconstruction / truth / error here.</p>`;
  }
}

function renderMetrics() {
  const m = run.metrics || {};
  document.querySelector("#metrics tbody").innerHTML = METRIC_ROWS
    .filter(([k]) => m[k] != null)
    .map(([k, label, dp]) => `<tr><th>${label}</th><td>${Number(m[k]).toFixed(dp)}</td></tr>`)
    .join("");
}

// Load the anatomical/recon base and, for the error view, an overlay on top.
async function showLayer(layer) {
  const opacity = parseFloat(document.getElementById("opacity").value);
  if (layer === "error") {
    // base = ground truth (gray), overlay = signed error (diverging colormap)
    await nv.loadVolumes([{ url: baseUrl + "truth.nii.gz", colormap: "gray" }]);
    await nv.addVolumeFromUrl({ url: baseUrl + "error.nii.gz", colormap: "warm", opacity });
    const ov = nv.volumes[nv.volumes.length - 1];
    ov.cal_min = 0; ov.cal_max = 0.05; // ppm; tune to data
    nv.updateGLVolume();
  } else {
    const url = layer === "truth" ? baseUrl + "truth.nii.gz" : baseUrl + "recon.nii.gz";
    await nv.loadVolumes([{ url, colormap: "gray" }]);
    const vol = nv.volumes[0];
    vol.cal_min = -0.1; vol.cal_max = 0.1; // ppm display window; tune to data
    nv.updateGLVolume();
  }
}

document.getElementById("layer").addEventListener("change", (e) => showLayer(e.target.value));
document.getElementById("opacity").addEventListener("input", (e) => {
  for (let i = 1; i < nv.volumes.length; i++) nv.setOpacity(i, parseFloat(e.target.value));
  nv.updateGLVolume();
});

init();
