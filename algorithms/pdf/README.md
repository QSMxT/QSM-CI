# PDF

Projection onto Dipole Fields: models the background field as external dipoles.

- **Stage:** `bfr` (totalfield → localfield, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Liu et al., NMR Biomed 2011 · doi:[10.1002/nbm.1670](https://doi.org/10.1002/nbm.1670)

## How QSM-CI runs it

```bash
qsmxt bgremove pdf /input/totalfield.nii.gz -m /input/mask.nii.gz -o /output/localfield.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `tol` | 1e-4 | convergence tolerance |

_Citations/DOIs are auto-generated best-effort references and should be verified._
