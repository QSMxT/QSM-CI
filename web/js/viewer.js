// Submission detail + NiiVue viewer. Module scope (needs `import`); shared helpers via window.QSM.
import { Niivue } from "https://unpkg.com/@niivue/niivue@0.57.0/dist/index.js";

const { loadRuns, METRICS, STAGE_LABEL, val, fmt } = window.QSM;

const STAGE_COLOR = {
  "field-mapping": "bg-indigo-50 text-indigo-700 ring-indigo-100",
  bfr: "bg-violet-50 text-violet-700 ring-violet-100",
  dipole: "bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-100",
};

const runId = new URLSearchParams(location.search).get("run");
let nv, run, baseUrl, win;

function badge(text, cls) {
  return `<span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${cls}">${text}</span>`;
}

async function init() {
  const runs = await loadRuns();
  run = runs.find((r) => r.id === runId);
  if (!run) { document.getElementById("sub-title").textContent = "Run not found"; return; }

  document.getElementById("sub-title").textContent = run.name;
  const stageCls = STAGE_COLOR[run.stage] || "bg-gray-100 text-gray-600 ring-gray-200";
  document.getElementById("sub-badges").innerHTML =
    badge(STAGE_LABEL[run.stage] || run.stage, stageCls) +
    badge(run.mode === "composed" ? "Composed pipeline" : "Isolated", "bg-gray-100 text-gray-600 ring-gray-200") +
    (run.status === "DNF" ? badge("DNF", "bg-red-50 text-red-600 ring-red-100") : "");
  const bits = [];
  if (run.artifact) bits.push(`scored artifact <code class="text-gray-700">${run.artifact}</code>`);
  if (run.runtime_s != null) bits.push(`runtime ${run.runtime_s.toFixed(1)}s`);
  if (run.image) bits.push(`image <code class="text-gray-700">${run.image}</code>`);
  document.getElementById("sub-meta").innerHTML = bits.join(" · ");

  renderMetrics();

  if (run.status === "DNF") {
    viewerPlaceholder("This run did not produce a valid output (DNF).");
    return;
  }

  baseUrl = `results/${run.id}/`;
  win = run.kind === "field"
    ? { lo: -1.0, hi: 1.0, elo: 0, ehi: 0.5 }
    : { lo: -0.1, hi: 0.1, elo: 0, ehi: 0.05 };

  nv = new Niivue({
    isColorbar: true, textHeight: 0.03, show3Dcrosshair: false, crosshairWidth: 0.75,
    backColor: [0, 0, 0, 1],
    onLocationChange: (d) => { document.getElementById("intensity").innerHTML = d.string; },
  });
  await nv.attachTo("gl1");
  nv.setSliceType(nv.sliceTypeMultiplanar);

  wireControls();
  try { await showLayer("recon"); } catch (e) {
    viewerPlaceholder("Interactive volumes aren't available for this run.");
  }
}

function renderMetrics() {
  const m = run.metrics || {};
  document.getElementById("metrics-sub").textContent =
    run.mode === "composed" ? "Final χ map vs. ground truth" : `${run.artifact || "output"} vs. ground truth`;
  const order = Object.keys(METRICS).filter((k) => m[k] != null);
  document.getElementById("metrics-body").innerHTML = order.map((k) => {
    const meta = METRICS[k];
    const arrow = meta.better === "higher" ? "↑" : "↓";
    const hero = k === "xsim" || k === "nrmse";
    return `<tr>
      <td class="py-2.5 text-gray-500">${meta.label}
        <span class="text-gray-300" title="${meta.better} is better">${arrow}</span></td>
      <td class="py-2.5 text-right tabular-nums ${hero ? "font-bold text-gray-900" : "font-medium text-gray-700"}">${fmt(m[k], k)}</td>
    </tr>`;
  }).join("") || `<tr><td class="py-3 text-gray-400">No metrics.</td></tr>`;
}

function viewerPlaceholder(msg) {
  document.getElementById("gl1").style.display = "none";
  document.querySelector("#layer-tabs").parentElement.style.display = "none";
  document.getElementById("viewer-note").innerHTML =
    `<div class="flex h-[480px] items-center justify-center rounded-xl bg-gray-50 text-sm text-gray-400 px-6 text-center">${msg}</div>`;
}

function wireControls() {
  const tabs = document.querySelectorAll("#layer-tabs button");
  const setActive = (layer) => tabs.forEach((t) =>
    t.className = "rounded-md px-3 py-1 transition " +
      (t.dataset.layer === layer ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"));
  tabs.forEach((t) => t.addEventListener("click", () => { setActive(t.dataset.layer); showLayer(t.dataset.layer); }));
  setActive("recon");
  document.getElementById("opacity").addEventListener("input", (e) => {
    for (let i = 1; i < nv.volumes.length; i++) nv.setOpacity(i, parseFloat(e.target.value));
    nv.updateGLVolume();
  });
}

async function showLayer(layer) {
  const opacity = parseFloat(document.getElementById("opacity").value);
  if (layer === "error") {
    await nv.loadVolumes([{ url: baseUrl + "truth.nii.gz", colormap: "gray" }]);
    nv.volumes[0].cal_min = win.lo; nv.volumes[0].cal_max = win.hi;
    await nv.addVolumeFromUrl({ url: baseUrl + "error.nii.gz", colormap: "warm", opacity });
    const ov = nv.volumes[nv.volumes.length - 1];
    ov.cal_min = win.elo; ov.cal_max = win.ehi;
    nv.updateGLVolume();
  } else {
    await nv.loadVolumes([{ url: baseUrl + (layer === "truth" ? "truth.nii.gz" : "recon.nii.gz"), colormap: "gray" }]);
    nv.volumes[0].cal_min = win.lo; nv.volumes[0].cal_max = win.hi;
    nv.updateGLVolume();
  }
}

init();
