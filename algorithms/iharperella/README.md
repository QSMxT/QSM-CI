# iHARPERELLA

Improved HARPERELLA: iterative integrated unwrapping + background removal on wrapped phase.

- **Stage:** `unwrap+bfr` (phase → localfield, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Li et al., NeuroImage 2014 · doi:[10.1016/j.neuroimage.2014.08.029](https://doi.org/10.1016/j.neuroimage.2014.08.029)

## How QSM-CI runs it

```bash
qsmxt bgremove iharperella /input/phase.nii.gz -m /input/mask.nii.gz -o /output/localfield.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `radius` | 5.0 | SMV kernel radius (mm) |
| `max_iter` | 100 | iterations |
| `tol` | 1e-4 | tolerance |

_Citations/DOIs are auto-generated best-effort references and should be verified._
