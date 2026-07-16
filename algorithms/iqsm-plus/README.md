# iQSM+

An orientation-adaptive, single-step deep-learning method that reconstructs susceptibility directly
from the raw wrapped MRI phase.

- **Stage:** `end-to-end` (phase → chimap, ppm)
- **Engine:** [iQSM+](https://github.com/sunhongfu/iQSM_Plus) — PyTorch, **CPU-only** (no GPU)
- **Reference:** Gao Y., Xiong Z., Shan S., Liu Y., Rong P., Li M., Wilman A.H., Pike G.B., Liu F., Sun H. (2024). *Plug-and-Play Latent Feature Editing for Orientation-Adaptive Quantitative Susceptibility Mapping Neural Networks.* Medical Image Analysis, 95, 103160. (DOI: [10.1016/j.media.2024.103160](https://doi.org/10.1016/j.media.2024.103160))

## Why `end-to-end`

iQSM+ is a **single-step** network: a single forward pass takes the raw wrapped phase and produces
susceptibility, folding phase unwrapping, background-field removal and dipole inversion into one
learned model (`inference.run_iqsm_plus` runs the LoT-Unet on the wrapped phase and returns χ). So it
consumes **phase** (+ magnitude, mask, params) and produces **chimap** — the `end-to-end` span, not a
single pipeline stage.

## Orientation-adaptive

iQSM+ extends iQSM with **orientation-adaptive latent feature editing (OA-LFE)** blocks that learn to
encode the acquisition-orientation vector and inject it into the network's latent features. This lets
non-axial acquisitions (oblique, sagittal, coronal) reconstruct correctly without any resampling. The
B0 direction is therefore a genuine model input, not just a dipole-kernel parameter — `run.sh` passes
it via `--b0-dir` from `$QSMCI_B0_DIR` (or `params.json` `B0_dir`), defaulting to axial `0 0 1`.

## Units

The QSM-CI `phase` artifact is the **raw wrapped phase in radians**, which is exactly what iQSM+
expects — the network does its own unwrapping (`run_iqsm_plus`'s phase convention is
`phase = -ΔB·γ·TE`, matching the default `phase_sign = -1`). **No conversion to ppm is applied on
input.** The output χ is already in **ppm**, the QSM-CI `chimap` unit.

## Multi-echo

QSM-CI's `phase` is 4D (`x, y, z, echo`). It is handed to iQSM+ via `--echo_4d`, and the engine's own
CLI runs inference once per echo and combines the per-echo χ with **magnitude × TE² weighted
averaging** (the magnitude and echo times come from `magnitude.nii.gz` and `$QSMCI_TE`). Single-echo
(3D) phase uses the same flag. The per-echo combination is intentionally left to the upstream CLI
rather than re-implemented here.

## How QSM-CI runs it

```bash
python /opt/iQSM_Plus/run.py \
  --echo_4d /input/phase.nii.gz \
  --te <TE_s …> \
  --mag /input/magnitude.nii.gz \
  --mask /input/mask.nii.gz \
  --b0 <B0_T> \
  --b0-dir <B0_dir> \
  [--voxel-size <x y z>] \
  --output /output
mv /output/iQSM_plus.nii.gz /output/chimap.nii.gz
```

`--te` is in seconds (from `$QSMCI_TE`), `--b0` in Tesla (`$QSMCI_B0`), `--b0-dir` from
`$QSMCI_B0_DIR`, and `--voxel-size` from `$QSMCI_VOXEL_SIZE` (iQSM+ otherwise reads the NIfTI header).
The engine writes `iQSM_plus.nii.gz`; `run.sh` renames it to the canonical `chimap.nii.gz`.

The pretrained weights (`iQSM_plus.pth`, `LoTLayer_chi.pth`) are **baked into the image** at build
time (`python run.py --download-checkpoints`, from HuggingFace `sunhongfu/iQSM_Plus`) so the scoring
run works fully offline (`--network none`).

## Parameters

iQSM+ has no runtime tunables exposed here — it uses fixed pretrained weights. The acquisition-derived
inputs (B0 direction, B0 strength, echo times, voxel size) come from `params.json` /
`QSMCI_*` env vars.

## Building the image

The environment image bundles the iQSM+ engine (`git clone` at a pinned commit) and its weights; it
must be built before scoring works (the run phase has no network, so weights cannot be fetched at run
time). QSM-CI builds this folder's `Dockerfile` at score time, so no manual push is required for the
leaderboard — a push is only needed for later Zenodo publishing:

```bash
docker build -t ghcr.io/astewartau/qsm-ci/iqsm-plus:v1 algorithms/iqsm-plus
docker push  ghcr.io/astewartau/qsm-ci/iqsm-plus:v1
```

## License

The upstream repository ships no license file; used here **with the authors' permission**.

_Citations/DOIs are auto-generated best-effort references and should be verified._
