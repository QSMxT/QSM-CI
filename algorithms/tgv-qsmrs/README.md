# TGV

Total Generalized Variation single-step reconstruction: total field -> susceptibility, doing its own background field removal.

- **Stage:** `bfr+dipole` (totalfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Langkammer et al., NeuroImage 2015 · doi:[10.1016/j.neuroimage.2015.02.041](https://doi.org/10.1016/j.neuroimage.2015.02.041)

## How QSM-CI runs it

```bash
qsmxt invert tgv /input/totalfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `iterations` | from the voxel size | iterations |
| `alpha1` | 0.00212 | first-order weight, rad at the echo time |
| `alpha0` | 0.00636 | second-order weight, rad at the echo time |

_Citations/DOIs are auto-generated best-effort references and should be verified._
