# qsmart-matlab fidelity check

Does the `qsmart-matlab` container compute what the authors' MATLAB computes? The shared harness
[`../../../fidelity/matlab/`](../../../fidelity/matlab/README.md) runs the pinned image and the same
`recon.m` in licensed R2023b with the real toolboxes, and compares every intermediate and the final χ.
[`config.sh`](config.sh) lays out QSMART's dependencies as BUILD.md §1–2 does, and its setup hook
wraps the image's own `N4BiasFieldCorrection` so every run uses one N4 binary, and diffs QSM-CI's
patched files against the authors' originals (`reports/deviations.diff`). The latest results are in
[`REPORT.md`](REPORT.md).

```bash
export FID_QSMART=/path/to/QSMART FID_SUN=/path/to/sunhongfu-QSM FID_STI=/path/to/STISuite_V3.0/STISuite_V3.0
FID_CASES="sim=/path/sim/inputs invivo=/path/acquisition/inputs" \
  bash fidelity/matlab/submit.sh qsmart-matlab all
```

Rerun it whenever `recon.m`, `vasculature_mask_qsmci.m` or the image changes.
