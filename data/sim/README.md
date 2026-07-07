# Simulated track data

The **simulated** track uses a digital phantom with perfectly known field maps and susceptibility,
so every stage boundary can be scored against ground truth.

## Layout

A dataset is a directory with two parts (see [`../../CONTRACT.md`](../../CONTRACT.md) and
[`../../stages.yml`](../../stages.yml)):

```
<dataset>/inputs/        phase.nii.gz  magnitude.nii.gz  mask.nii.gz  params.json   (public boundary)
<dataset>/groundtruth/   totalfield.nii.gz  localfield.nii.gz  chimap.nii.gz  dseg.nii.gz   (held out)
```

- `inputs/` — the public entry boundary (raw phase/mag/mask/params).
- `groundtruth/` — the per-stage scoring targets *and* the boundaries mounted at run time as
  isolated-mode inputs (a `dipole` submission is fed the true `localfield`, etc.). **Never committed.**

Two datasets:

- **`dev/`** — a small phantom for local development (`data/sim/dev/`), generated on demand. Both
  `inputs/` and `groundtruth/` may be released openly. Git-ignored (regenerate with the commands
  below).
- **`scoring/`** — the phantom submissions are scored on. Sourced from the QSM.rs reference dataset
  on **OSF** (private project [`y8adf`](https://osf.io/y8adf/), "QSM Rust Test Data" — a single
  `bids.zip` with raw data + `derivatives/qsm-forward` ground truth). `scripts/fetch_dataset.sh`
  downloads it with `OSF_TOKEN`, unzips, and packs it into `inputs/` + `groundtruth/`. The CI caches
  the zip (`OSF_ZIP=.osfcache/bids.zip`). Held out — submissions never get the token, so they can't
  see `groundtruth/`.

## Generating a dataset

From the `qsm-forward` checkout (`~/repos/qsm/qsm-forward`), simulate a BIDS phantom, then flatten
it into the QSM-CI artifact layout with `scripts/pack_dataset.py`:

```bash
# 1. simulate (from the qsm-forward source dir so `import qsm_forward` resolves)
python -c "import numpy as np, qsm_forward as q; \
  chi=q.generate_susceptibility_phantom([96,96,60],0,0.005,[6,6,5,4],[0.05,0.1,-0.1,0.2]); \
  q.generate_bids(q.TissueParams(chi=chi, voxel_size=np.array([1.,1.,1.])), \
  q.ReconParams(subject='1', B0=3.0, TEs=np.array([0.004,0.012,0.02,0.028]), \
  voxel_size=np.array([1.,1.,1.]), peak_snr=100, random_seed=42), '/tmp/BIDS', save_field=True)"

# 2. pack into inputs/ + groundtruth/
python scripts/pack_dataset.py /tmp/BIDS data/sim/dev
```

## Head phantom (the real scoring dataset)

The simple cylinder phantom above validates **plumbing only** (`totalfield == localfield`, so BFR
has nothing to remove; `dseg` labels {0,1}, so region χ metrics are degenerate).

The **scoring** dataset uses `qsm-forward`'s realistic head model, which gives:

- `totalfield ≠ localfield` (air/skull background sources) — so the BFR stage is meaningful.
- the full label set — 1–6 DGM, 7 thalamus, 8 WM, 9 GM, 10 CSF, 11 blood, 13 bone, 14 air,
  15 muscle, 16 calcification — so every region χ metric populates.

A head-phantom BIDS run was packed into `data/sim/scoring/` with `pack_dataset.py` (7T, 4 echoes,
1mm, 164×205×205) and drives the current leaderboard in `results/index.json`. It confirmed the
expected behaviour: the no-BFR baseline is catastrophic (localfield xsim ≈ 0.04), SHARP recovers it
(≈ 0.61), and the per-stage ordering (TKD > Tikhonov) survives composition. **Record the exact
`qsm-forward` head-model invocation here** once the canonical challenge phantom is fixed, and upload
its `groundtruth/` to OSF (held out).
