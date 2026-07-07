# Simulated track data

The **simulated** track uses a digital phantom with a perfectly known susceptibility map, so the
full metric suite (region-specific NRMSE, DGM linearity, calcification, streaking) is meaningful.

## What's here (public)

`public/` holds the **inputs** given to every submission (mounted at `/input`):

- `phase.nii.gz` — wrapped multi-echo phase (radians)
- `magnitude.nii.gz` — magnitude
- `mask.nii.gz` — brain mask
- `params.json` — TE / B0 / B0_dir / voxel_size (see [`../../CONTRACT.md`](../../CONTRACT.md))

## What's held out (never committed)

The ground truth is **not** in this repo, so submissions cannot overfit to it:

- `chimap.nii.gz` — true susceptibility map (ppm)
- `dseg.nii.gz` — tissue segmentation (labels used for region-specific metrics)

It lives on **OSF** and is pulled by `.github/workflows/evaluate.yml` using the `OSF_TOKEN` repo
secret, mirroring how QSM.rs' integration-test data is stored (OSF project `y8adf`).

- OSF project: `<TODO: fill in QSM-CI OSF project id>`
- Files: `sim/groundtruth/chimap.nii.gz`, `sim/groundtruth/dseg.nii.gz`

## How the data was generated

Generated with [`qsm-forward`](https://github.com/astewartau/qsm-forward) (local checkout at
`~/repos/qsm/qsm-forward`), the same forward model behind QSM.rs' `derivatives/qsm-forward`.

- Grid / voxel size: `<TODO>`
- Field strength B0: `<TODO>` T, B0_dir `[0, 0, 1]`
- Echo times: `<TODO>`
- Segmentation labels: 1–6 deep gray matter, 7 thalamus, 8 WM, 9 GM, 10 CSF, 11 blood,
  16 calcification (matches QSM.rs `ChallengeMetrics`).

Record the exact `qsm-forward` invocation here once the phantom is finalized so the dataset is
reproducible.
