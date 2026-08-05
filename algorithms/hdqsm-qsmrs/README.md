# HD-QSM

Hybrid data-fidelity QSM: a two-stage linear inversion where an L1 stage produces a discrepancy map that reweights a second L2 stage.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Lambert et al., Magn Reson Med 2022 · doi:[10.1002/mrm.29218](https://doi.org/10.1002/mrm.29218)

## How QSM-CI runs it

```bash
qsmxt invert hdqsm /input/localfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `alpha_l2` | 1e-4 | L2-stage TV weight |
| `mu1_l2` | 1e-2 | L2-stage gradient-consistency weight |
| `max_iter_l1` | 20 | stage-1 (L1) iterations |
| `max_iter_l2` | 80 | stage-2 (L2) iterations |

_Citations/DOIs are auto-generated best-effort references and should be verified._
