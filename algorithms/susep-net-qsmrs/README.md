# SUSEP-Net (QSM.rs)

SUSEP-Net as QSM.rs runs it: the authors' trained weights exported to ONNX (QSM.rs's
`scripts/onnx-export/`) and run by `qsmxt separate susep-net` on QSM.rs's ONNX engine (tract, CPU).

- **Stage:** `chi-separation`: reads `localfield` (ppm), `chimap` (χ_total, ppm), `r2prime` (Hz) and `mask`; writes `chi-para.nii.gz` (χ+ ≥ 0) and `chi-dia.nii.gz` (|χ−|), both ppm.
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs).
- **Original:** [`susep-net`](../susep-net) runs the authors' own code and weights; the two entries share `algorithm: susep-net`, so they form a port parity pair. First look: [`fidelity/dl/`](../../fidelity/dl).
- **Image:** `qsmxt:v10.0.0-models`, the QSMxT v10.0.0 release image with the ONNX weights baked in ([`_qsmxt/models.Dockerfile`](../_qsmxt/models.Dockerfile)), since the run has no network.
- **Reference:** Li, Gao, Sun et al., "SUSEP-Net: simulation-supervised contrastive learning for susceptibility source separation via a sub-voxel QSM network", arXiv:2506.13293, 2025. · doi:[10.48550/arXiv.2506.13293](https://doi.org/10.48550/arXiv.2506.13293)

## How QSM-CI runs it

```bash
# -o is a PREFIX: qsmxt writes {prefix}_desc-paramagnetic_Chimap.nii and _desc-diamagnetic_
# (the positive magnitude |χ−|, as the contract wants) uncompressed; publish the two gzipped.
B0DIR="${QSMCI_B0_DIR:-0 0 1}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
qsmxt separate susep-net \
  --qsm "$IN/chimap.nii.gz" --local-field "$IN/localfield.nii.gz" --r2prime "$IN/r2prime.nii.gz" \
  -m "$IN/mask.nii.gz" -o "$WORK/cs" --b0-direction $B0DIR --field-strength "${QSMCI_B0:-3}"
gzip -c "$WORK/cs_desc-paramagnetic_Chimap.nii" > "$OUT/chi-para.nii.gz"
gzip -c "$WORK/cs_desc-diamagnetic_Chimap.nii" > "$OUT/chi-dia.nii.gz"
```
