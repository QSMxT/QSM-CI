# Building matlab-bfrnet (compiled MATLAB deep-learning net → MATLAB Runtime)

Compile `recon.m` on a machine with **MATLAB + MATLAB Compiler + Deep Learning Toolbox** (R2026a).
Same MCR-deployment pattern as `../matlab-sti-iharperella/BUILD.md` (bundled NIfTI toolbox, OS
gzip, no JVM), **but this is a deep-learning method**, so two extra requirements:

1. **Deep Learning Toolbox is required *at compile time*.** `recon.m` calls `image3dInputLayer`,
   `layerGraph`, `replaceLayer`, `assembleNetwork`, and `predict`, and the bundled `BFRnet.mat`
   deserialises to a trained `DAGNetwork`. MATLAB Compiler *can* deploy DL networks onto the
   license-free MATLAB Runtime, but only if the Deep Learning Toolbox is present on the build
   machine when you run `mcc` (it packages the required runtime libraries into the CTF archive).
   The Runtime itself needs no toolbox license — but the **build box does**.
2. **The trained weights are fetched from the authors' Dropbox — NOT committed** (they're large and
   not ours to redistribute). See step 1 below.

Stage: `bfr` — consumes `totalfield` (ppm) + `mask` + `params`; produces `localfield` (ppm).
BFRnet predicts the **background** field; `recon.m` returns `local = (totalfield − background)·mask`.

## Units — clean scalar mapping, no TE/B0
BFRnet operates entirely in **ppm**: input total field (ppm) → predicted background field (ppm) →
local field (ppm). The network never sees TE, B0, or B0_dir, so no Hz↔ppm conversion is needed (the
QSM-CI `totalfield`/`localfield` artifacts are already ppm). `params.json` is read only for
completeness; voxel size rides on the NIfTI header.

## 1. Fetch build-time deps (not committed)
```bash
# NIfTI toolbox (same as the STI submission) — gitignored via algorithms/*/nifti/
cp -r /path/to/NIfTI_20140122   algorithms/matlab-bfrnet/nifti

# BFRnet trained network from the authors' Dropbox ("data & checkpoints" link in the repo README:
#   https://github.com/sunhongfu/BFRnet  ->  https://www.dropbox.com/sh/q678oapc65evrfa/...
# The demo uses BFRnet_L2_64PS_24BS_45Epo_NewHCmix.mat, which contains a `net` variable.
# Rename to BFRnet.mat (recon.m loads S.net from BFRnet.mat) and drop it in the folder.
cp /path/to/BFRnet_L2_64PS_24BS_45Epo_NewHCmix.mat  algorithms/matlab-bfrnet/BFRnet.mat
```
`BFRnet.mat` is gitignored (large binary weights, redistributed only with author permission). If the
Dropbox link ever dies, the same network is mirrored under `sunhongfu/deepMRI/BFRnet`.

## 2. Compile
```bash
cd algorithms/matlab-bfrnet
matlab -batch "addpath('shims'); addpath('nifti'); \
  mcc('-m','recon.m','-a','nifti','-a','shims','-a','BFRnet.mat','-o','recon','-d','.')"
```
`-a BFRnet.mat` bundles the trained network into the CTF; `recon.m` finds it at run time via
`ctfroot`. `-a nifti` bundles the NIfTI I/O. `-a shims` bundles the `padarray` replacement (the
Runtime has no Image Processing Toolbox — same shim as the STI submission, `shims/` IS committed
because it's ours). mcc auto-includes the Deep Learning Toolbox runtime because `recon.m`'s DL calls
are on the traced path.

## 3. Bake the MCR image and push
```bash
docker build -t ghcr.io/astewartau/qsm-ci/matlab-bfrnet:v1 .   # FROM matlab-runtime:r2026a + COPY recon
docker push  ghcr.io/astewartau/qsm-ci/matlab-bfrnet:v1
```
Then make the GHCR package public. The `Dockerfile` is gitignored (`algorithms/matlab-*/Dockerfile`)
so CI pulls the prebuilt image rather than rebuilding a licensed mcc binary it cannot reproduce.

## Notes
- BFRnet's 3 pooling levels require input dims divisible by 8; `recon.m` zero-pads ('post') to the
  next multiple of 8 and crops the prediction back — matching the repo's `ZeroPadding(tfs, 8)` step.
- Inference is CPU (`'ExecutionEnvironment','cpu'`) so it runs on any Runtime host; ~16 GB RAM is
  recommended for a whole-brain volume (per the upstream demo). Switch to `'auto'`/`'gpu'` if the
  evaluation host has a supported GPU.
