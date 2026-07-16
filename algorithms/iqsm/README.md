# iQSM

Instant single-step quantitative susceptibility mapping from raw MRI phase using Laplacian-enabled
deep neural networks (LoT-Unet).

- **Stage:** `end-to-end` (phase → chimap, ppm)
- **Engine:** [iQSM](https://github.com/sunhongfu/iQSM) — PyTorch, **CPU-only**
- **Reference:** Gao Y., Xiong Z., Fazlollahi A., Nestor P.J., Vegh V., Nasrallah F., Winter C., Pike G.B., Crozier S., Liu F., Sun H. (2022). *Instant tissue field and magnetic susceptibility mapping from MRI raw phase using Laplacian enhanced deep neural networks.* NeuroImage, 259, 119410. (DOI: [10.1016/j.neuroimage.2022.119410](https://doi.org/10.1016/j.neuroimage.2022.119410))

## Why `end-to-end`

iQSM is a **single-step** deep network: a large-stencil Laplacian-preprocessed LoT-Unet maps the
**raw wrapped phase** straight to susceptibility χ. Phase unwrapping, background-field removal, and
dipole inversion all happen inside the network — there is no separate field-mapping / BFR / dipole
stage. So the method consumes `phase`, `magnitude`, `mask`, `params` and produces `chimap`, i.e. the
`end-to-end` span (see `stages.yml`). Evidence in the source: `inference.py::run_iqsm()` loads the
wrapped phase NIfTI and feeds it (plus TE and B0) to the network, whose output is saved as
`iQSM.nii.gz` — no field map is ever consumed.

## Units

- **Input** is **raw wrapped phase in radians**, which is exactly what iQSM ingests (it applies the
  sign convention and Laplacian preprocessing internally). QSM-CI's `phase.nii.gz` is in radians, so
  it is passed through unchanged. iQSM does **not** take a field map — do not convert to ppm.
- **Output** χ is already in **ppm** (the network is trained to output ppm susceptibility). No
  rescaling is applied; `run.sh` copies iQSM's `iQSM.nii.gz` verbatim to `chimap.nii.gz`.

## Multi-echo handling

iQSM runs the network **per echo** and combines the per-echo χ maps with **magnitude × TE²**
weighting (falling back to TE²-only weighting when magnitude is absent). `run.sh` hands the 4D
`phase.nii.gz` and 4D `magnitude.nii.gz` to the repo's own CLI (`run.py --echo_4d --mag --te …`),
which performs exactly that combination — it is **not** re-implemented here. A 3D (single-echo)
`phase.nii.gz` is handled by the same code path.

## B0 direction

Base iQSM assumes an **axial** acquisition (B0 ≈ `[0, 0, 1]`); the network takes no B0-direction
argument, so `QSMCI_B0_DIR` is informational only and is not passed through. Only the field strength
(`QSMCI_B0` / `params.json` `B0`) and the echo time(s) (`QSMCI_TE` / `params.json` `TE`) are fed to
the network.

## How QSM-CI runs it

```bash
python /opt/iqsm/run.py \
  --echo_4d /input/phase.nii.gz \
  --te <TE …> \
  --mag /input/magnitude.nii.gz \
  --mask /input/mask.nii.gz \
  --b0 <B0> --no-iqfm \
  --output /output/iqsm_run
cp /output/iqsm_run/iQSM.nii.gz /output/chimap.nii.gz
```

`--no-iqfm` skips the optional tissue-field (iQFM) output — QSM-CI only scores `chimap.nii.gz`.

The four pretrained checkpoints (~16 MB each) are **baked into the image** at build time
(`run.py --download-checkpoints`, pulling from HuggingFace `sunhongfu/iQSM`) so the scoring run works
fully offline (`--network none`). The iQSM source and its `checkpoints/` are baked together under
`/opt/iqsm` because iQSM resolves the checkpoint directory relative to its own source location, not
relative to the mounted `/algo`.

## Parameters

iQSM has no runtime tunables exposed here — it uses fixed pretrained weights. The acquisition-derived
inputs are the field strength `B0` and echo time(s) `TE`, taken from `params.json` /
`QSMCI_B0` / `QSMCI_TE`. Mask erosion (iQSM default 3 voxels) and phase-sign convention (iQSM default)
are left at their upstream defaults.

## Building the image

The environment image is built from this folder's `Dockerfile` at score time (QSM-CI's
`pipeline.build_env` builds any folder that has a `Dockerfile`), so a manual push is not required for
the leaderboard. To build/push manually (e.g. for later Zenodo publishing):

```bash
docker build -t ghcr.io/astewartau/qsm-ci/iqsm:v1 algorithms/iqsm
docker push  ghcr.io/astewartau/qsm-ci/iqsm:v1
```

_Citations/DOIs are auto-generated best-effort references and should be verified. The DOI here was
verified against CrossRef (NeuroImage 259, 119410); note the upstream repo's README BibTeX lists a
different DOI, which does not resolve to this paper._
