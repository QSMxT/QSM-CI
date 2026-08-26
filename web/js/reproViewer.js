// Side-by-side χ-map viewer for the Harmonization (repro) track. The reproducibility question is
// visual as much as numeric: does a pipeline give the SAME susceptibility map on two different
// acquisitions of the same head? So this shows one pipeline's recon on two acquisitions at once,
// crosshair-synced, straight from the public HuggingFace volumes repo.
//
// Volume URLs are DETERMINISTIC from (pipeline identity, acquisition) — no index.json entry needed:
//   repro/<acq>/<pipelineId with + -> _>-cmp-<acq>__recon.nii.gz
// (matches pipeline.py's run id `<slug ~-joined>-cmp-<phantom>` and publish_volumes' _name/_subdir.)
import { Niivue } from "https://unpkg.com/@niivue/niivue@0.57.0/dist/index.js";

const HF_BASE = "https://huggingface.co/datasets/qsmxt/qsm-ci-volumes/resolve/main/";

export function reconUrl(pipelineId, acq) {
  return `${HF_BASE}repro/${acq}/${pipelineId.replaceAll("+", "_")}-cmp-${acq}__recon.nii.gz`;
}

let nvA = null, nvB = null;

function _mk(canvasId) {
  const nv = new Niivue({
    backColor: [0, 0, 0, 1], show3Dcrosshair: true, crosshairWidth: 0.6,
    isColorbar: true, textHeight: 0.04,
  });
  nv.attachTo(canvasId);
  nv.setSliceType(nv.sliceTypeMultiplanar);
  return nv;
}

// Called once when the Reconstructions subtab first renders (canvases must be in the DOM).
export function initReproViewer() {
  if (nvA) return;
  nvA = _mk("repro-gl-a");
  nvB = _mk("repro-gl-b");
  try { nvA.broadcastTo(nvB, { "2d": true, "3d": true }); nvB.broadcastTo(nvA, { "2d": true, "3d": true }); } catch (_) {}
}

async function _load(nv, url, win) {
  const status = document.getElementById(nv === nvA ? "repro-status-a" : "repro-status-b");
  try {
    await nv.loadVolumes([{ url, colormap: "gray", cal_min: -win, cal_max: win }]);
    if (status) status.textContent = "";
    return true;
  } catch (e) {
    // A DNF'd (pipeline, acquisition) has no recon on HF -> 404. Say so instead of a blank canvas.
    if (nv.volumes?.length) nv.removeVolumeByIndex(0);
    if (status) status.textContent = "no reconstruction for this pipeline + acquisition";
    return false;
  }
}

// (re)load both panels for the current pipeline + the two chosen acquisitions.
export async function loadReproPair(pipelineId, acqA, acqB, win = 0.12) {
  if (!nvA) return;
  await Promise.all([
    _load(nvA, reconUrl(pipelineId, acqA), win),
    _load(nvB, reconUrl(pipelineId, acqB), win),
  ]);
}

// Re-window both panels without reloading (χ maps are ppm; slider drives ±win).
export function setReproWindow(win) {
  for (const nv of [nvA, nvB]) {
    for (const v of nv?.volumes || []) { v.cal_min = -win; v.cal_max = win; }
    nv?.updateGLVolume();
  }
}
