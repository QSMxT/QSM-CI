# NeXtQSM (QSM.rs)

NeXtQSM as QSM.rs runs it: the authors' trained weights exported to ONNX (QSM.rs's
`scripts/onnx-export/`) and run by `qsmxt invert nextqsm` on QSM.rs's ONNX engine (tract, CPU).

- **Stage:** `bfr+dipole`: reads `totalfield` (ppm) and `mask`; writes `chimap.nii.gz` (ppm).
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs).
- **Original:** [`nextqsm`](../nextqsm) runs the authors' own code and weights; the two entries share `algorithm: nextqsm`, so they form a port parity pair. First look: [`fidelity/dl/`](../../fidelity/dl).
- **Image:** `qsmxt:v10.0.0-models-2`, the QSMxT v10.0.0 release image with the ONNX weights baked in ([`_qsmxt/models.Dockerfile`](../_qsmxt/models.Dockerfile)), since the run has no network.
- **Reference:** Cognolato et al., Med Image Anal 2023 · doi:[10.1016/j.media.2022.102700](https://doi.org/10.1016/j.media.2022.102700)

## How QSM-CI runs it

```bash
# B0 direction and field strength from params.json (QSMCI_* env, CONTRACT.md).
B0DIR="${QSMCI_B0_DIR:-0 0 1}"
qsmxt invert nextqsm "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
  --b0-direction $B0DIR --field-strength "${QSMCI_B0:-3}"
```
