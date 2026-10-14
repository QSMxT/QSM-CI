# Laplacian field mapping (QSM.rs)

Multi-echo B0 field mapping by Laplacian phase unwrapping (Schofield & Zhu, *Optics Letters* 2003)
through the QSMxT / QSM.rs engine's `qsmxt fieldmap laplacian`: each echo is unwrapped on its own,
then the echoes are combined into a single B0 estimate. The alternative to `romeo-qsmrs`.

- **Stage:** `field-mapping` — reads `phase` (multi-echo), `magnitude`, `mask`, `params`; writes
  `totalfield.nii.gz` (ppm)
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs) (Rust), CPU
- **Reference:** Schofield & Zhu, *Optics Letters* 2003 ·
  doi:[10.1364/OL.28.001194](https://doi.org/10.1364/OL.28.001194)
- **Image:** `ghcr.io/astewartau/qsm-ci/qsmxt:v10.0.0`, the shared QSMxT engine image
  ([`algorithms/_qsmxt`](../_qsmxt))

## How QSM-CI runs it

`run.sh` is a single `qsmxt fieldmap laplacian` call over the input phase, magnitude, mask and
`params.json`, writing the total field in ppm.

```bash
qsm-ci run laplacian-qsmrs --phase phase.nii.gz --magnitude magnitude.nii.gz --mask mask.nii.gz --params params.json -o totalfield.nii.gz
```

## Settings

| option | value | meaning |
|---|---|---|
| `--laplacian-solver` | `dct` (default) | unweighted least-squares Poisson solve with Neumann boundaries (DCT); `fft` is the zero-padded FFT solve of STI Suite's `MRPhaseUnwrap` |
| `--b0-estimation` | `weighted-avg` (passed explicitly) | per-echo field estimates averaged with per-voxel weights |
| `--b0-weight-type` | `phase-snr` (default) | weights from the magnitude-derived phase SNR of each echo |

Phase-offset removal and bipolar correction are not applied with Laplacian unwrapping.
