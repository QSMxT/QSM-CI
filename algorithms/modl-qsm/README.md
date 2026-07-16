# MoDL-QSM

Model-based deep learning for quantitative susceptibility mapping — a dipole-inversion network that
unrolls a gradient-descent solver of the QSM forward model, alternating a learned CNN prior with
data-consistency terms built from the dipole kernel.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [MoDL-QSM](https://github.com/Ruimin-Feng/MoDL-QSM) — legacy **TensorFlow 1.15 / Keras 2.2.5 / Python 3.6**, **CPU-only**
- **Reference:** Feng R., Zhao J., Wang H., Yang B., Feng J., Shi Y., Zhang M., Liu C., Zhang Y., Zhuang J., Wei H. (2021). *MoDL-QSM: Model-based deep learning for quantitative susceptibility mapping.* NeuroImage, 240, 118376. (DOI: [10.1016/j.neuroimage.2021.118376](https://doi.org/10.1016/j.neuroimage.2021.118376); arXiv: [2101.08413](https://arxiv.org/abs/2101.08413))

## Why `dipole`

MoDL-QSM inverts the dipole convolution: it takes the **tissue (local) field** and produces
**susceptibility**. Its `model_test` entry point (`test/test_tools.py`) consumes the tissue field
`phi`, the brain mask, the voxel size, and the B0 direction, and returns the susceptibility map. The
dipole kernel is generated **internally** from the B0 direction (`test_tools.dipole_kernel`) and
enforced through data-consistency `A`/`AH` operators in the unrolled network (`model/MoDL_QSM.py`).
So the method consumes `localfield` and produces `chimap` — the `dipole` stage.

## Units

The QSM-CI `localfield` is the tissue field already **in ppm** (normalized by B0). This is exactly
MoDL-QSM's `phi` input: the repo's example `test_data.mat` `phi` arrays span ~±0.1–0.2 (ppm), not
radians. The field is fed to the network **unchanged**, and the output susceptibility (in ppm) is
written **unchanged** to `chimap.nii.gz`.

## Input normalization — `NormFactor.mat`

MoDL-QSM ships `NormFactor.mat`, the **train-set mean/std** (`CosTrnMean`, `CosTrnStd`) used to
normalize the network's working variables. It **must** be applied or the output scale is wrong.
Rather than normalizing the raw input in the runner, MoDL-QSM bakes these factors **into the Keras
graph**: `define_generator()` normalizes each intermediate susceptibility estimate with
`(x - CosTrnMean) / CosTrnStd` before the CNN prior and de-normalizes with `x * CosTrnStd + CosTrnMean`
after (see `model/MoDL_QSM.py`). `model_test` loads `../NormFactor.mat` relative to the current
directory, so `recon.py` runs from `$MODL_QSM_HOME/test` to guarantee the factors are found and
applied.

## Output — χ33

The network emits **two channels**: χ33 (the STI susceptibility-tensor component along B0 — STI-
flavored but comparable to scalar QSM) and the field induced by the χ13/χ23 terms. We keep channel 0
(**χ33**) as the `chimap`.

## How QSM-CI runs it

```bash
python recon.py /input /output
```

`recon.py` reads `localfield.nii.gz` + `mask.nii.gz`, takes the voxel size (NIfTI header) and B0
direction (`$QSMCI_B0_DIR` / `params.json` `B0_dir`, default axial `0 0 1`), calls MoDL-QSM's
`model_test` (which builds the dipole kernel and applies `NormFactor.mat`), and writes χ33 to
`chimap.nii.gz` on the input grid, in ppm.

## Parameters

MoDL-QSM has no runtime tunables — it uses fixed pretrained weights (`logs/last.h5`, ~1.8 MB,
committed in-repo). The only acquisition-derived inputs are the B0 direction and voxel size, used to
build the dipole kernel.

## Building the image

The environment image must be built and pushed before scoring works (the run phase has no network,
so the repo — code + weights + `NormFactor.mat` — cannot be fetched at run time; the Dockerfile
`git clone`s it at build time):

```bash
docker build -t ghcr.io/astewartau/qsm-ci/modl-qsm:v1 algorithms/modl-qsm
docker push  ghcr.io/astewartau/qsm-ci/modl-qsm:v1
```

QSM-CI builds this folder's `Dockerfile` at score time to produce the environment image; the mounted
`run.sh` / `recon.py` are executed inside it.

## License

The MoDL-QSM repository declares no license. Used here with the authors' permission.

_Citations/DOIs are auto-generated best-effort references and should be verified._
