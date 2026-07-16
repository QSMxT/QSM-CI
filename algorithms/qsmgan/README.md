# QSMGAN

Efficient and accurate QSM dipole inversion by a 3D U-Net generator refined with a
Wasserstein GAN (WGAN-GP) and an increased receptive field.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMGAN](https://github.com/mmorri10/QSMGAN-LupoLab) — PyTorch (legacy), **CPU-only**
- **Reference:** Chen Y., Jakary A., Avadiappan S., Hess C.P., Lupo J.M. (2020). *QSMGAN: Improved Quantitative Susceptibility Mapping using 3D Generative Adversarial Networks with increased receptive field.* NeuroImage, 207, 116389. (DOI: [10.1016/j.neuroimage.2019.116389](https://doi.org/10.1016/j.neuroimage.2019.116389))

## Why `dipole`

QSMGAN learns the dipole inversion only. Upstream, the network is fed the
background-removed **local field** (their pipeline runs SEPIA for background field
removal first) and outputs susceptibility. It does not do field mapping or background
removal itself, so it maps exactly onto the QSM-CI `dipole` stage: consumes
`localfield.nii.gz`, `mask.nii.gz`, `params.json`; produces `chimap.nii.gz`.

The architecture is a 3D U-Net **generator** (`UNet3D`, 4 pool layers, LeakyReLU,
BatchNorm, tanh output head) trained first with an L1 objective and then refined
adversarially by a WGAN-GP discriminator. We load the WGAN-refined generator
(`WGAN_i64o48/net_best.pt`) — the checkpoint the upstream NIFTI inference script uses.

## Source: official repo has no code

The official repository [LupoLab-UCSF/QSMGAN](https://github.com/LupoLab-UCSF/QSMGAN)
is **README only** — no code and no weights. This submission uses the working fork
[mmorri10/QSMGAN-LupoLab](https://github.com/mmorri10/QSMGAN-LupoLab), which carries the
PyTorch code and the committed checkpoints (`UNet3D_i64o48.zip`, `WGAN_i64o48.zip`).
Both repos are MIT-licensed (the fork's LICENSE is © 2021 Melanie A. Morrison).

## Units

QSMGAN expects the SEPIA **local field in ppm**. QSM-CI's `localfield.nii.gz` is already
a background-removed local field in ppm on the mask grid, which is exactly that — no
rescaling of the input units is applied. The network's own internal normalization
(`input_scale = 100`; output head `tanh`, `output_scale = 10`, so
`chi = arctanh(net_out) / 10`) is reproduced verbatim in `recon.py` from the upstream
config. Output is in ppm on the input grid.

## Patch-based inference and stitching

Inference is patch-based with an **increased receptive field**: a 64³ input patch is
mapped to a 48³ output patch (a center receptive-field crop) — the "i64o48" scheme.
`recon.py` tiles the volume by non-overlapping 48³ **output** patches; each output
patch's 64³ **input** patch is the same center with an 8-voxel context margin per side,
zero-padded at the volume edges. Output patches are placed back and clipped to the
volume bounds, so arbitrary volume shapes (not just multiples of 48) are handled. The
result is masked by `mask.nii.gz`.

Unlike the upstream `QsmPatchDataHD`, we deliberately **skip** its hard-coded
`[1, 1, 1/0.8]` resolution zoom (that is specific to one 0.8 mm HD scanner); QSM-CI
data is already on the mask grid, so the output stays on the input grid.

## Legacy PyTorch pinning

The published code targets "PyTorch >= 0.4" and the released checkpoints are the legacy
(pre-1.6, tar/pickle) `torch.save` format. The image pins **`torch==1.1.0`** (CPU) on
**Python 3.7** — contemporaneous with the 2019 release and the lowest legacy torch that
both loads the checkpoint and has working NumPy interop. (The `torch==0.4.1` prebuilt
wheel was compiled *without* NumPy support, so `torch.from_numpy()` raises at runtime;
1.1.0 is used instead.) The `UNet3D` generator is **not** rewritten — its definition is
vendored verbatim into `recon.py` and the state_dict is loaded as-is.

## Parameters

QSMGAN has no runtime tunables — it uses fixed pretrained weights. The B0 direction is
not needed (the network learned the dipole implicitly for axial acquisition).

## Building the image

The environment image must be built and pushed before scoring works (the run phase has
no network, so weights cannot be fetched at run time). The ~30 MB checkpoints are cloned
from the fork and unzipped at **build** time:

```bash
docker build -t ghcr.io/astewartau/qsm-ci/qsmgan:v1 algorithms/qsmgan
docker push  ghcr.io/astewartau/qsm-ci/qsmgan:v1
```

QSM-CI builds this folder's `Dockerfile` at score time to produce the environment; your
`run.sh` + `recon.py` are then mounted read-only at `/algo` and run offline.

_Citations/DOIs are auto-generated best-effort references and should be verified._
