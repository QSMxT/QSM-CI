# MoDL-QSM (QSM.rs)

MoDL-QSM as QSM.rs runs it: the authors' trained weights exported to ONNX (QSM.rs's
`scripts/onnx-export/`) and run by `qsmxt invert modl-qsm` on QSM.rs's ONNX engine (tract, CPU).

- **Stage:** `dipole`: reads `localfield` (ppm) and `mask`; writes `chimap.nii.gz` (ppm).
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs).
- **Original:** [`modl-qsm`](../modl-qsm) runs the authors' own code and weights; the two entries share `algorithm: modl-qsm`, so they form a port parity pair. First look: [`fidelity/dl/`](../../fidelity/dl).
- **Image:** `qsmxt:v12.2.0-models-1`, the QSMxT v12.2.0 release image with the ONNX weights baked in ([`_qsmxt/models.Dockerfile`](../_qsmxt/models.Dockerfile)), since the run has no network.
- **Reference:** Feng et al., NeuroImage 2021 · doi:[10.1016/j.neuroimage.2021.118376](https://doi.org/10.1016/j.neuroimage.2021.118376)

## How QSM-CI runs it

```bash
# B0 direction and field strength from params.json (QSMCI_* env, CONTRACT.md).
B0DIR="${QSMCI_B0_DIR:-0 0 1}"
qsmxt invert modl-qsm "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
  --b0-direction $B0DIR --field-strength "${QSMCI_B0:-3}"
```

## Amplitude

MoDL-QSM's χ comes out at about 0.5× the reference on QSM-CI's simulation and in vivo data (slope
0.49 / 0.53, correlation 0.85 / 0.79), and about 0.5–0.7× on the authors' own demo outputs (2016
challenge 0.53; their Prisma data 0.72). On the authors' outputs the reverse slope (reference on χ)
is ≈1, i.e. the released network shrinks values towards the mean. Input units (ppm) and wiring match
the authors' code (the QSM.rs port matches it to 0.0002 % NRMSE). QSM-CI reports the method as
published; its deep-grey-matter slope shows the effect.
