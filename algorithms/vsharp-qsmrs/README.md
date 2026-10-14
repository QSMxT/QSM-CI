# V-SHARP

Variable-radius SHARP: background removal by SMV filtering with a spatially varying kernel radius
(the largest kernel that fits at each voxel).

Since qsmxt v10.0.0 the SMV high-pass is **not deconvolved** by default, which is what QSM-CI runs.
Earlier releases (and so earlier leaderboard entries for this method) undid it with a truncated-SVD
deconvolution; `--set deconvolve=true` restores that, and `threshold` applies only then.

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
| `deconvolve` | false | undo the SMV high-pass with a TSVD deconvolution |
| `threshold` | 0.2 | deconvolution (TSVD) threshold; only used with `deconvolve=true` |
| `max_radius` | 12.0 | largest (starting) SMV kernel radius (mm) |
| `min_radius` | 1.0 | smallest SMV kernel radius (mm) |

_Citations/DOIs are auto-generated best-effort references and should be verified._
