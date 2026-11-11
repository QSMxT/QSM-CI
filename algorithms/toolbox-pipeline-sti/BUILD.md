# Building toolbox-pipeline-sti (compiled MATLAB → MATLAB Runtime)

STI Suite 3.0's QSM_GUI iLSQR pipeline ("Thresholding", "V-SHARP", "iLSQR"), from the echoes to χ:
the reference side of pipeline parity for QSMxT's `sti-suite-ilsqr` pipeline (QSMxT/QSM-CI#421).
The recipe is [`../ilsqr-sti/BUILD.md`](../ilsqr-sti/BUILD.md)'s (licensed R2023b + MATLAB
Compiler with the Image Processing Toolbox, R2023b Runtime), with the whole chain in `recon.m`.

Stage: `pipeline`. It consumes `phase`, `magnitude` and `params` and produces `chimap` (ppm).

## 1. Fetch build-time deps (not committed)
```bash
cp -r /path/to/NIfTI_20140122                            algorithms/toolbox-pipeline-sti/nifti
cp -r /path/to/STISuite_V3.0/Core_Functions_P            algorithms/toolbox-pipeline-sti/sti
cp /path/to/STISuite_V3.0/GUI_Functions_P/PolishMask.p   algorithms/toolbox-pipeline-sti/sti/
```
Not `Support_Functions/`: its `wavelet_src/sfb3D_A.m` breaks mcc's parser, and the one function the
pipeline needs from it, `thresh_tool`'s starting level, is written out in `recon.m` (its figure
cannot run headless). [`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`) is the same
recipe as a script.

## 2. Compile
```bash
cd algorithms/toolbox-pipeline-sti
matlab -batch "addpath('nifti'); addpath('sti'); mcc('-m','recon.m','-a','sti','-o','recon','-d','.')"
```
`-a sti` bundles every `.p`, and `recon.m`'s `%#function` pragma names the Image Processing
Toolbox functions the pcode calls (as `ilsqr-sti`). On Bunya the harness does this as a Slurm job
(`fidelity/matlab/submit.sh toolbox-pipeline-sti build`).

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/sti-pipeline:v1 .   # needs ./recon from §2
podman push  ghcr.io/astewartau/qsm-ci/sti-pipeline:v1
```
Pin `image:` in `algorithm.yml` by the pushed digest and run the fidelity check
([`fidelity/REPORT.md`](fidelity/REPORT.md)).
