# QSMnet

A pretrained 3D U-Net for quantitative susceptibility mapping by deep-learning **dipole inversion**.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMnet](https://github.com/SNU-LIST/QSMnet) — TensorFlow **1.14 / Python 3.7**, **CPU-only** (legacy TF1 stack, not ported to TF2)
- **Reference:** Yoon J., Gong E., Chatnuntawech I., Bilgic B., Lee J., Jung W., Ko J., Jung H., Setsompop K., Zaharchuk G., Kim E.Y., Pauly J., Lee J. (2018). *Quantitative susceptibility mapping using deep neural network: QSMnet.* NeuroImage, 179, 199–206. (DOI: [10.1016/j.neuroimage.2018.06.030](https://doi.org/10.1016/j.neuroimage.2018.06.030))

## Why `dipole`

QSMnet is a single 3D U-Net that maps a **local (tissue) field** directly to **susceptibility** — it
performs only the dipole inversion, with no field-mapping or background-field-removal step. So it
consumes `localfield` and produces `chimap`, i.e. the `dipole` stage. (`Code/inference.py` loads one
network, feeds it the tissue field `phs_tissue`, and saves the susceptibility output in ppm.)

## Units & normalization

The QSM-CI `localfield` is the local/tissue field already **in ppm** (normalized by B0) — the same
quantity QSMnet was trained on (`phs_tissue`). We therefore **do not** re-run the authors' MATLAB
Laplacian-unwrap / V-SHARP preprocessing (that produced `phs_tissue` for their own pipeline; our
`localfield` is the equivalent).

The network additionally expects its input scaled by the **dataset mean/std stored with the
checkpoint** (`norm_factor_<name>.mat`). The wrapper applies

```
field_n = (field - input_mean) / input_std        # feed to the net
chi     = label_std * prediction + label_mean      # de-normalize output -> ppm
```

QSMnet was trained at **1 mm isotropic**; the U-Net has four max-pool/deconv levels, so the wrapper
zero-pads each dimension up to a multiple of **16** before inference and crops back afterwards. The
output is masked and written on the input NIfTI's affine/header (voxel size + orientation preserved).

## How QSM-CI runs it

```bash
bash run.sh                      # -> python qsmnet_infer.py localfield.nii.gz mask.nii.gz chimap.nii.gz
```

`qsmnet_infer.py` drives the repo's `network_model.qsmnet_deep` (leaky-ReLU) with the baked checkpoint.

## Weights (baked at build time from Google Drive)

The pretrained checkpoint lives on the authors' Google Drive (see the repo's
`Checkpoints/download_network.sh`). It is fetched with **`gdown`** at **build time** (network is on
during build, off at scoring) and extracted into the image, so inference runs fully offline
(`--network none`). `gdown` handles Google Drive's large-file confirm-token.

## Parameters

QSMnet has no runtime tunables — it uses fixed pretrained weights. Voxel size and orientation are
carried by the input NIfTI affine.

## Building the image

The environment image must be built and pushed before scoring works (the run phase has no network, so
weights cannot be fetched at run time). QSM-CI also builds this folder's Dockerfile at score-time, so
no manual push is strictly required for the leaderboard:

```bash
docker build -t ghcr.io/astewartau/qsm-ci/qsmnet:v1 algorithms/qsmnet
docker push  ghcr.io/astewartau/qsm-ci/qsmnet:v1
```

_Citations/DOIs are auto-generated best-effort references and should be verified._
