# LSQR (minimally regularised)

The dipole inversion solved as one large least-squares system, leaning on LSQR's minimum-norm
property rather than an explicit regularisation term. Two extra sets of unknowns make that work: a
**residual field** `r` (weight `w`) that absorbs field the dipole model cannot explain, and a single
**global offset** `c` for any constant shift left by background removal.

```
minimise ‖ W · ( M[ F⁻¹(D · F χ) + c ] + w·r − b ) ‖₂   over  [χ; r; c]
```

`w` is the only thing regularising the solve, so on its own this method streaks — it is included
here as a baseline and because it is the seed [HEIDI](../heidi-qsmrs) builds on.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Schweser et al., Medical Physics 2010 ([10.1118/1.3481505](https://doi.org/10.1118/1.3481505))

## How QSM-CI runs it

```bash
qsmxt invert lsqr /input/localfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz \
  --b0-direction <B0_dir> --b0 <B0> [--magnitude /input/magnitude.nii.gz]
```

## Parameters

| parameter | default | description |
|---|---|---|
| `residual_weighting` | field-scaled | weight `w` on the residual field; unset scales with B0 (0.2/9.4 per tesla), `0` drops the term |
| `global_offset` | `true` | fit a single global field offset alongside χ |
| `tol` | 1e-5 | LSQR convergence tolerance |
| `max_iter` | 400 | LSQR iterations |
