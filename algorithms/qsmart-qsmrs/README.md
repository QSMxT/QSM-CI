# QSMART

Vessel-aware two-stage QSM reconstruction. **Total field → susceptibility** (`bfr+dipole` span):
QSMART performs its own spatially-dependent background field removal and vasculature-aware
regularization (Frangi vessel detection + a signed distance field), so it consumes the total field
rather than a background-removed local field.

- **Stage:** `bfr+dipole` (totalfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) implementation (`qsmxt qsmart`, added in v9.2.0)
- **Reference:** Yaghmaie et al., NMR Biomed 2021 · doi:[10.1002/nbm.4442](https://doi.org/10.1002/nbm.4442)

## How QSM-CI runs it

```bash
qsmxt qsmart /input/totalfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz \
  --b0-direction <B0> --field-strength <B0_T> --echo-time <TE1> [--magnitude /input/magnitude.nii.gz]
```

Magnitude is optional (drives vasculature detection; a uniform fallback is used if absent).
