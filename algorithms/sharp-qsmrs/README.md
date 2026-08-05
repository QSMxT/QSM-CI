# SHARP

Sophisticated Harmonic Artifact Reduction for Phase data: SMV deconvolution.

- **Stage:** `bfr` (totalfield → localfield, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Schweser et al., NeuroImage 2011 · doi:[10.1016/j.neuroimage.2010.10.070](https://doi.org/10.1016/j.neuroimage.2010.10.070)

## How QSM-CI runs it

```bash
qsmxt bgremove sharp /input/totalfield.nii.gz -m /input/mask.nii.gz -o /output/localfield.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `threshold` | 0.02 | deconvolution threshold |
| `radius_factor` | 0.5 | × min voxel size |

_Citations/DOIs are auto-generated best-effort references and should be verified._
