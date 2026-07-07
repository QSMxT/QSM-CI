# RTS

Rapid Two-Step QSM: streaking-artifact reduction via a fast ADMM split.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Kames et al., NeuroImage 2018 · doi:[10.1016/j.neuroimage.2018.07.043](https://doi.org/10.1016/j.neuroimage.2018.07.043)

## How QSM-CI runs it

```bash
qsmxt invert rts /input/localfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `delta` | 1.0 | regularization |
| `mu` | 1.0 | smoothness |
| `max_iter` | 1000 | iterations |

_Citations/DOIs are auto-generated best-effort references and should be verified._
