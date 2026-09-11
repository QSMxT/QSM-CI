# TFI (QSM.rs)

Preconditioned Total Field Inversion (Liu et al., *MRM* 2017): a single-step method that inverts
the total field directly to susceptibility over the whole field of view, doing background-field
removal and dipole inversion jointly. A preconditioner (χ = P·y, larger outside the brain) keeps the
large out-of-brain background susceptibility well-conditioned, with MEDI-style L1 morphology
regularisation weighted by the magnitude.

- **Stage:** `bfr+dipole` span — reads `totalfield` (ppm), `mask`, `magnitude` (used for the SNR
  data weight and the morphology mask when present), `params` (B0 direction); writes
  `chimap.nii.gz` (ppm)
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs) (Rust) — `qsmxt invert tfi`,
  which takes the total field in ppm directly (no radians conversion, unlike MEDI)
- **Reference:** Liu et al., *Magn Reson Med* 2017;78(1):303-315 ·
  doi:[10.1002/mrm.26946](https://doi.org/10.1002/mrm.26946)
- **Image:** `ghcr.io/astewartau/qsm-ci/qsmxt:v9.11.0`, the shared QSMxT engine image
  ([`algorithms/_qsmxt`](../_qsmxt)). This folder has no Dockerfile: `run.sh` is mounted at run
  time.

## How QSM-CI runs it

`run.sh` reads `B0_dir` from `params.json` with `jq`, adds `--magnitude` when the file is present,
forwards `lambda` / `precond` overrides from `config.json` (the `qsm-ci run --set` path), and calls

```bash
qsmxt invert tfi totalfield.nii.gz -m mask.nii.gz -o chimap.nii.gz --b0-direction <B0> [--magnitude magnitude.nii.gz] [--lambda L] [--precond P]
```

Locally:

```bash
qsm-ci run tfi-qsmrs --totalfield totalfield.nii.gz --mask mask.nii.gz --magnitude magnitude.nii.gz -o chimap.nii.gz
qsm-ci run tfi-qsmrs … --set lambda=1e-5
```

## Parameters

| parameter | default | tuned (sim) | description |
|---|---|---|---|
| `lambda` | 7.5e-5 | 1e-5 | data-fidelity weight (MEDI's default; larger = closer data fit, less regularisation) |
| `precond` | 30 | — | preconditioner: susceptibility scaling outside the brain mask (~30 for in-vivo air, Liu 2017) |
