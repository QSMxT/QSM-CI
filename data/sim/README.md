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
- **`scoring/`** — the phantom submissions are scored on. `groundtruth/` is held out on **OSF** and
  pulled by CI (`scripts/fetch_dataset.sh`, `OSF_TOKEN`). Overfitting is prevented because
  submissions never see it.

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

## ⚠️ Head phantom needed for the real challenge

The simple cylinder phantom above validates the **plumbing** but not the science:

- `totalfield == localfield` (no background sources) — so the BFR stage has nothing to remove.
- `dseg` has only labels {0, 1} — so the region-specific χ metrics (tissue/blood/DGM/calcification)
  are degenerate.

The scoring dataset must use `qsm-forward`'s realistic head model (`ChiModelMIX` + segmentation +
air/skull background sources) so that `totalfield ≠ localfield` and the full label set (1–6 DGM,
7 thalamus, 8 WM, 9 GM, 11 blood, 16 calcification) is present. Sourcing/curating that head model is
the remaining data task; record the exact `qsm-forward` invocation here once finalized.
