# NDI

Nonlinear Dipole Inversion: gradient-descent solve of a nonlinear (wrapped-phase) data term; effectively tuning-free.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Polak et al., NMR Biomed 2020 · doi:[10.1002/nbm.4271](https://doi.org/10.1002/nbm.4271)

## How QSM-CI runs it

```bash
qsmxt invert ndi /input/localfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `tau` | 2.0 | gradient-descent step size |
| `alpha` | 1e-5 | L2 regularization weight |
| `max_iter` | 200 | iterations |

_Citations/DOIs are auto-generated best-effort references and should be verified._
