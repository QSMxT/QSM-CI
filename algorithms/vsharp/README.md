# V-SHARP

Variable-radius SHARP: SMV deconvolution with a spatially varying kernel radius.

- **Stage:** `bfr` (totalfield → localfield, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Wu et al., Magn Reson Med 2012 _(DOI: TODO — verify)_

## How QSM-CI runs it

```bash
qsmxt bgremove vsharp /input/totalfield.nii.gz -m /input/mask.nii.gz -o /output/localfield.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `threshold` | 0.02 | deconvolution threshold |
| `max_radius_factor` | 0.5 | × min voxel size |
| `min_radius_factor` | 0.0 | × max voxel size |

_Citations/DOIs are auto-generated best-effort references and should be verified._
