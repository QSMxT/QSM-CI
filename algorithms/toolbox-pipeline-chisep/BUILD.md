# Building toolbox-pipeline-chisep (compiled MATLAB → MATLAB Runtime)

The χ-separation toolbox v1.1.3's own pipeline (`Chisep_script.m`), from the echoes to χ+ and χ−:
the reference side of pipeline parity for QSMxT's `chi-sep-ilsqr` and `chi-sep-medi` pipelines
(QSMxT/QSM-CI#421), with `method` set to `ilsqr` or `medi`. `chi-sepnet`'s pipeline is a separate
submission, because its networks run in Python.

Stage: `pipeline`, with `r2prime` (a measured R2′, Hz) as an optional input that this submission
requires. The recipe follows [`../chisep-ilsqr/BUILD.md`](../chisep-ilsqr/BUILD.md) and
[`../chisep-medi/BUILD.md`](../chisep-medi/BUILD.md), plus MEDI's BET (bet2 mex) and mritools'
ROMEO.

## 1. Fetch build-time deps (not committed)
[`fidelity/config.sh`](fidelity/config.sh) `fid_assemble` is the recipe: the NIfTI toolbox, STI Suite
3.0's `Core_Functions_P`, the χ-separation toolbox's `functions/` and `utils/`, MEDI 2024.11.26's
top-level functions plus `bet2/`, and `matlab/ROMEO.m` from the mritools 4.7.1 release
(`mritools_ubuntu-22.04_4.7.1.tar.gz`, korbinian90/CompileMRI.jl). mritools 4.7.1 (May 2025) is the
release that was current when the toolbox's v1.1.3 files were made (July 2025); the script names no
version.

## 2. Compile
```bash
matlab -batch "cd medi/bet2; runmex"; rm medi/bet2/runmex.m
matlab -batch "addpath(genpath('chisep')); addpath('sti','medi','medi/bet2','mritools','nifti'); \
  mcc('-m','recon.m','-a','sti','-a','chisep','-a','medi','-a','mritools','-o','recon','-d','.')"
```
On Bunya: `fidelity/matlab/submit.sh toolbox-pipeline-chisep build`.

## 3. Bake the image and push
The [`Dockerfile`](Dockerfile) adds mritools 4.7.1's `romeo` binary at `/opt/mritools/bin/romeo`
(`MRITOOLS_ROMEO`, which recon.m passes to ROMEO.m as its `command`).
```bash
podman build -t ghcr.io/astewartau/qsm-ci/chisep-pipeline:v1 .
podman push  ghcr.io/astewartau/qsm-ci/chisep-pipeline:v1
```
Pin `image:` by digest and run the fidelity check. The licensed runs need `FID_MRITOOLS` (the
unpacked release) so that they call the same `romeo`.
