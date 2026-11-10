# V-SHARP

Variable-radius SHARP: background removal by SMV filtering with a spatially varying kernel radius
(the largest kernel that fits at each voxel).

As in QSMxT, the SMV high-pass is not deconvolved by default. The simulation-tuned run deconvolves it
with a truncated SVD at threshold 0.05 (`--set deconvolve=true`); `threshold` applies only with
deconvolution.

- **Stage:** `bfr` (totalfield → localfield, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Wu et al., Magn Reson Med 2012 · doi:[10.1002/mrm.23000](https://doi.org/10.1002/mrm.23000)

## How QSM-CI runs it

```bash
qsmxt bgremove vsharp /input/totalfield.nii.gz -m /input/mask.nii.gz -o /output/localfield.nii.gz --b0-direction <B0> --deconvolve false
```

## Parameters

| parameter | default | description |
|---|---|---|
| `deconvolve` | false (sim-tuned: true) | undo the SMV high-pass with a TSVD deconvolution |
| `threshold` | 0.05 | deconvolution (TSVD) threshold; only used with `deconvolve=true` |
| `max_radius` | 12.0 | largest (starting) SMV kernel radius (mm) |
| `min_radius` | 1.0 | smallest SMV kernel radius (mm) |

_Citations/DOIs are auto-generated best-effort references and should be verified._
