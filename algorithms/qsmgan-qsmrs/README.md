# QSMGAN (QSM.rs)

QSMGAN as QSM.rs runs it: the authors' trained weights exported to ONNX (QSM.rs's
`scripts/onnx-export/`) and run by `qsmxt invert qsmgan` on QSM.rs's ONNX engine (tract, CPU).

- **Stage:** `dipole`: reads `localfield` (ppm) and `mask`; writes `chimap.nii.gz` (ppm).
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs).
- **Original:** [`qsmgan`](../qsmgan) runs the authors' own code and weights; the two entries share `algorithm: qsmgan`, so they form a port parity pair. First look: [`fidelity/dl/`](../../fidelity/dl).
- **Image:** `qsmxt:v10.0.0-models-2`, the QSMxT v10.0.0 release image with the ONNX weights baked in ([`_qsmxt/models.Dockerfile`](../_qsmxt/models.Dockerfile)), since the run has no network.
- **Reference:** Chen et al., NeuroImage 2020 · doi:[10.1016/j.neuroimage.2019.116389](https://doi.org/10.1016/j.neuroimage.2019.116389)

## How QSM-CI runs it

```bash
# B0 direction and field strength from params.json (QSMCI_* env, CONTRACT.md).
B0DIR="${QSMCI_B0_DIR:-0 0 1}"
qsmxt invert qsmgan "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
  --b0-direction $B0DIR --field-strength "${QSMCI_B0:-3}"
```
