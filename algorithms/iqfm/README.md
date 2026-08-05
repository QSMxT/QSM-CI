# iQFM

Instant tissue (local) field mapping from raw MRI phase using Laplacian-enabled deep neural networks
(LoT-Unet). iQFM is the **tissue-field output of the same network/repo as iQSM** — the `algorithms/iqsm/`
submission runs the identical repo with `--no-iqfm` to *skip* exactly this output; this submission
keeps it.

- **Stage:** `unwrap+bfr` (phase → localfield, ppm)
- **Engine:** [iQSM/iQFM](https://github.com/sunhongfu/iQSM) — PyTorch, **CPU-only**
- **Reference:** Gao Y., Xiong Z., Fazlollahi A., Nestor P.J., Vegh V., Nasrallah F., Winter C., Pike G.B., Crozier S., Liu F., Sun H. (2022). *Instant tissue field and magnetic susceptibility mapping from MRI raw phase using Laplacian enhanced deep neural networks.* NeuroImage, 259, 119410. (DOI: [10.1016/j.neuroimage.2022.119410](https://doi.org/10.1016/j.neuroimage.2022.119410))

## Why `unwrap+bfr`

iQFM is a **single-step** deep network: a large-stencil Laplacian-preprocessed LoT-Unet maps the
**raw wrapped phase** straight to the **local (tissue) field** — phase unwrapping *and*
background-field removal both happen inside the network, with no separate field-mapping / BFR stage.
So the method consumes `phase`, `magnitude`, `mask`, `params` and produces `localfield`, i.e. the
`unwrap+bfr` span (see `stages.yml`).

Evidence in the source (`inference.py::run_iqsm()` and `models/`): the same wrapped-phase input drives
two parallel LoT-Unet heads — one trained to output susceptibility χ (iQSM, saved as `iQSM.nii.gz`),
one trained to output the tissue field (iQFM, saved as `iQFM.nii.gz`). The iQFM head is the
"lfs" (local field shift) branch loaded from `iQFM_40_v2.pth` + `LoTLayer_lfs_40_v2.pth`. The upstream
README describes iQFM as "the local tissue field map (the background-field-removal result)", confirming
it is the **local** field (post-BFR), not the total field. This submission publishes `iQFM.nii.gz` as
the canonical `localfield.nii.gz`.

## Units

- **Input** is **raw wrapped phase in radians**, which is exactly what iQFM ingests (it applies the
  sign convention and Laplacian preprocessing internally). QSM-CI's `phase.nii.gz` is in radians, so
  it is passed through unchanged.
- **Output** is the tissue field already in **ppm** (B0-normalized). The LoT layer divides the
  Laplacian-derived field by `(B0 · TE)` (`models/unet_blocks.py`), removing the field-strength and
  echo-time dependence so the network is trained to output a ppm-scale field. Upstream confirms this:
  the repo README's LFS display window is "± 0.05 ppm". QSM-CI's `localfield` artifact is also **ppm**
  (`stages.yml`), so **no unit conversion is applied** — `run.sh` copies `iQFM.nii.gz` verbatim to
  `localfield.nii.gz`. (If the network had emitted Hz, a `field_ppm = field_Hz / (γ · B0)` conversion
  would be required; it does not, so none is.)

## Multi-echo handling

iQFM runs the network **per echo** and combines the per-echo field maps with **magnitude × TE²**
weighting (falling back to TE²-only weighting when magnitude is absent). `run.sh` hands the 4D
`phase.nii.gz` and 4D `magnitude.nii.gz` to the repo's own CLI (`run.py --echo_4d --mag --te …`),
which performs exactly that combination — it is **not** re-implemented here. A 3D (single-echo)
`phase.nii.gz` is handled by the same code path.

## Mask & B0 direction

iQFM **requires a brain mask** (run.py auto-skips iQFM when no `--mask` is given). QSM-CI always
provides `mask.nii.gz`, so iQFM always runs. Base iQSM/iQFM assumes an **axial** acquisition
(B0 ≈ `[0, 0, 1]`); the network takes no B0-direction argument, so `QSMCI_B0_DIR` is informational
only. Only the field strength (`QSMCI_B0` / `params.json` `B0`) and echo time(s) (`QSMCI_TE` /
`params.json` `TE`) are fed to the network.

## How QSM-CI runs it

```bash
python /opt/iqsm/run.py \
  --echo_4d /input/phase.nii.gz \
  --te <TE …> \
  --mag /input/magnitude.nii.gz \
  --mask /input/mask.nii.gz \
  --b0 <B0> \
  --output /output/iqfm_run
cp /output/iqfm_run/iQFM.nii.gz /output/localfield.nii.gz
```

Note the **absence** of `--no-iqfm` (the flag the iqsm submission uses to skip this output). `run.py`
still also writes `iQSM.nii.gz` (χ); this submission ignores it and publishes only the iQFM tissue
field.

The four pretrained checkpoints (~16 MB each) are **baked into the image** at build time
(`run.py --download-checkpoints`, pulling from HuggingFace `sunhongfu/iQSM`) so the scoring run works
fully offline (`--network none`). That download includes the iQFM weights (`iQFM_40_v2.pth`,
`LoTLayer_lfs_40_v2.pth`) alongside the iQSM ones, so the same step covers iQFM as-is. The source and
its `checkpoints/` are baked together under `/opt/iqsm` because the code resolves the checkpoint
directory relative to its own source location, not relative to the mounted `/algo`.

## Relationship to the iqsm image

This submission's `Dockerfile` is **byte-identical** to `algorithms/iqsm/Dockerfile` (same repo, same
pinned commit `bb163ef`, same weights). The two submissions differ only in `run.sh` (iqsm passes
`--no-iqfm` and publishes `chimap`; iqfm keeps the iQFM output and publishes `localfield`). For clarity
and independence this submission uses its own image tag `ghcr.io/astewartau/qsm-ci/iqfm:v1`, but it
could equivalently reuse `ghcr.io/astewartau/qsm-ci/iqsm:v1`.

## Parameters

iQFM has no runtime tunables exposed here — it uses fixed pretrained weights. The acquisition-derived
inputs are the field strength `B0` and echo time(s) `TE`, taken from `params.json` / `QSMCI_B0` /
`QSMCI_TE`. Mask erosion (default 3 voxels) and phase-sign convention (default) are left at their
upstream defaults.

## Building the image

The environment image is built from this folder's `Dockerfile` at score time (QSM-CI's
`pipeline.build_env` builds any folder that has a `Dockerfile`), so a manual push is not required for
the leaderboard. To build/push manually (e.g. for later Zenodo publishing):

```bash
docker build -t ghcr.io/astewartau/qsm-ci/iqfm:v1 algorithms/iqfm
docker push  ghcr.io/astewartau/qsm-ci/iqfm:v1
```

_Citations/DOIs are auto-generated best-effort references and should be verified. The DOI here was
verified against CrossRef (NeuroImage 259, 119410) — the same paper as iQSM, whose title covers both
"tissue field" (iQFM) and "magnetic susceptibility" (iQSM); note the upstream repo's README BibTeX
lists a different DOI (…119327), which does not resolve to this paper._
