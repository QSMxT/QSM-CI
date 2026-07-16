# BFRnet — deep-learning background field removal (QSM-CI `bfr`)

BFRnet is a 3D deep convolutional (Octave-convolution) network that removes the background field for
QSM. It is trained to cope with brains containing **significant pathological susceptibility sources**
(haemorrhage, calcification) where conventional BFR (V-SHARP, PDF, …) struggles.

- **Stage:** `bfr` — consumes `totalfield` (ppm), `mask`, `params`; produces `localfield` (ppm).
- **How it maps:** the network predicts the **background** field from the (masked) total field; the
  local tissue field is `totalfield − background`, masked. Everything is in ppm, so there is no
  Hz↔ppm conversion and the net never uses TE/B0/B0_dir.
- **Framework:** MATLAB R2019a+ with the **Deep Learning Toolbox**. The trained network is a MATLAB
  DAG network `.mat`. For QSM-CI it is compiled with the MATLAB Compiler and run on the license-free
  MATLAB Runtime (r2026a).

## Files
- `recon.m` — QSM-CI wrapper: loads `totalfield.nii.gz`, rebuilds the net input layer at the volume
  size, predicts the background field, writes `localfield.nii.gz`.
- `run.sh` — invokes the compiled `recon` binary on the MATLAB Runtime.
- `Dockerfile` — MCR image that bakes the compiled binary (gitignored; see BUILD.md).
- `BUILD.md` — local compile + weights-fetch steps a maintainer must run (this method needs a
  licensed MATLAB + Deep Learning Toolbox at compile time; it cannot be a plain Dockerfile).

## Weights
The trained network is **not committed**. Fetch it from the authors' Dropbox ("data & checkpoints"
link in the [BFRnet README](https://github.com/sunhongfu/BFRnet)), rename to `BFRnet.mat`, and bundle
it at compile time with `mcc -a` — see [BUILD.md](BUILD.md).

## Citation
Zhu X, Gao Y, Liu F, Crozier S, Sun H. *BFRnet: A deep learning-based MR background field removal
method for QSM of the brain containing significant pathological susceptibility sources.* Zeitschrift
für Medizinische Physik, 2022. doi:[10.1016/j.zemedi.2022.08.001](https://doi.org/10.1016/j.zemedi.2022.08.001)
