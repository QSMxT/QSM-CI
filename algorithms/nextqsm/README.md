# NeXtQSM

A complete pre-trained deep-learning pipeline for data-consistent quantitative susceptibility
mapping trained with hybrid data.

- **Stage:** `bfr+dipole` (totalfield → chimap, ppm)
- **Engine:** [NeXtQSM](https://github.com/QSMxT/nextqsm) — TensorFlow, **CPU-only** (no GPU, no ONNX)
- **Reference:** Cognolato F., O'Brien K., Jin J., Robinson S., Laun F.B., Barth M., Bollmann S. (2023). *NeXtQSM — A complete deep learning pipeline for data-consistent Quantitative Susceptibility Mapping trained with hybrid data.* Medical Image Analysis, 84, 102700. (DOI: [10.1016/j.media.2022.102700](https://doi.org/10.1016/j.media.2022.102700))

## Why `bfr+dipole`

NeXtQSM is a **complete** pipeline that goes from the total (tissue) field to susceptibility in two
learned steps: a background-field-removal U-Net followed by a data-consistent variational-network
dipole inversion. In `nextqsm/predict_all.py` both networks are loaded and run — `bf_network`
(background removal → `bf_logits`) and `vn` (the variational net → `vn_logits`, saved as the QSM
output). So the method consumes the **total field** and produces **susceptibility**, i.e. the
`bfr+dipole` span, not the `dipole`-only stage.

## Units

The QSM-CI `totalfield` is an unwrapped frequency map already **in ppm** (normalized by B0), which is
exactly what NeXtQSM expects ("an unwrapped frequency map, unitless and scaled to ppm"). No rescaling
is performed. NeXtQSM reads the voxel size from the NIfTI header; `run.sh` only passes the B0
direction for the dipole kernel.

## How QSM-CI runs it

```bash
nextqsm /input/totalfield.nii.gz /input/mask.nii.gz /output/chimap.nii.gz --b_vec <B0_dir>
```

`--b_vec` is taken from `$QSMCI_B0_DIR` (or `params.json` `B0_dir`), defaulting to axial `0 0 1`.

The ~150 MB pretrained weights are **baked into the image** at build time
(`nextqsm --download_weights`) so the scoring run works fully offline (`--network none`).

## Parameters

NeXtQSM has no runtime tunables — it uses fixed pretrained weights. The only acquisition-derived
input is the B0 direction (from `params.json` / `QSMCI_B0_DIR`), used to build the dipole kernel.

## Building the image

The environment image must be built and pushed before scoring works (the run phase has no network,
so weights cannot be fetched at run time):

```bash
docker build -t ghcr.io/astewartau/qsm-ci/nextqsm:v1 algorithms/nextqsm
docker push  ghcr.io/astewartau/qsm-ci/nextqsm:v1
```

_Citations/DOIs are auto-generated best-effort references and should be verified._
