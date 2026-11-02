# IR2QSM (QSM.rs)

IR2QSM as QSM.rs runs it: the authors' trained weights exported to ONNX (QSM.rs's
`scripts/onnx-export/`) and run by `qsmxt invert ir2qsm` on QSM.rs's ONNX engine (tract, CPU).

- **Stage:** `dipole`: reads `localfield` (ppm) and `mask`; writes `chimap.nii.gz` (ppm).
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs).
- **Original:** [`ir2qsm`](../ir2qsm) runs the authors' own code and weights; the two entries share `algorithm: ir2qsm`, so they form a port parity pair. First look: [`fidelity/dl/`](../../fidelity/dl).
- **Image:** `qsmxt:v10.0.0-models-2`, the QSMxT v10.0.0 release image with the ONNX weights baked in ([`_qsmxt/models.Dockerfile`](../_qsmxt/models.Dockerfile)), since the run has no network.
- **Reference:** Li et al., Med Phys 2025 · doi:[10.1002/mp.17747](https://doi.org/10.1002/mp.17747)
- **Determinism:** the ONNX export takes the decoder's noise-free branch (no inference-time AddNoise), so the output is deterministic; the original's counterpart is `ir2qsm` run with `--set add_noise=false`.

## How QSM-CI runs it

```bash
# B0 direction and field strength from params.json (QSMCI_* env, CONTRACT.md).
B0DIR="${QSMCI_B0_DIR:-0 0 1}"
qsmxt invert ir2qsm "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
  --b0-direction $B0DIR --field-strength "${QSMCI_B0:-3}"
```
