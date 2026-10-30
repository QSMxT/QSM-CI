# Building vsharp-sti (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler, with the Image Processing
Toolbox**, and bake it onto the R2023b MATLAB Runtime. R2023b because it is the licensed MATLAB the
fidelity check runs on ([`../../fidelity/matlab/`](../../fidelity/matlab/README.md)), so the
container and the reference runs share one release. Same patterns as `../qsmart-matlab/BUILD.md`
(bundled NIfTI toolbox, OS gzip, no JVM, STI Suite `.p` code, no toolbox shims).

Stage: `bfr` — consumes `totalfield` (ppm) + `mask` + `params`; runs `V_SHARP` → `localfield` (ppm).

## 1. Fetch build-time deps (not committed)
```bash
cp -r /path/to/NIfTI_20140122                          algorithms/vsharp-sti/nifti
cp -r /path/to/STISuite_V3.0/Core_Functions_P          algorithms/vsharp-sti/sti
```
`sti/` holds the STI Suite `.p` (real code) + `.m` (help-only stubs). Don't bundle
`Support_Functions/` wholesale — it contains a corrupt `wavelet_src/sfb3D_A.m` that breaks mcc's
parser, and V-SHARP doesn't need it. [`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`)
is the same recipe as a script.

## 2. Compile
```bash
cd algorithms/vsharp-sti
matlab -batch "addpath('nifti'); addpath('sti'); \
  mcc('-m','recon.m','-a','sti','-o','recon','-d','.')"
```
`-a sti` force-bundles every `.p` (mcc can't trace dependencies **into** pcode, so it would
otherwise miss the helper `.p` that `V_SHARP.p` calls at runtime). For the same reason,
`recon.m` names the Image Processing Toolbox functions the pcode calls in a `%#function` pragma
(`padarray`). They were found by profiling a licensed run (`fidelity/matlab/submit.sh vsharp-sti trace`).
Check that `unresolvedSymbols.txt` is empty and `requiredMCRProducts.txt` lists the Image
Processing Toolbox (35010). The harness does this compile as a Slurm job
(`submit.sh vsharp-sti build`) and keeps the log in `reports/build.txt`.

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/matlab-sti-vsharp:v2 .   # needs ./recon from §2
podman push  ghcr.io/astewartau/qsm-ci/matlab-sti-vsharp:v2
```
Keep the package public, pin `image:` in `algorithm.yml` by the pushed digest, and rerun the
fidelity check ([`fidelity/REPORT.md`](fidelity/REPORT.md)). The [`Dockerfile`](Dockerfile) is the
R2023b Runtime base (pinned by digest) plus `recon`; it sets `LD_LIBRARY_PATH`, which the r2023b
base doesn't.

Images: `v1` (R2026a Runtime, toolbox shims whose greyscale `imdilate`/`imerode` wrapped round at
the volume border; its Dockerfile was `FROM matlab-runtime:r2026a` + `COPY recon` + `chmod +x`);
`v2` (R2023b, the real toolboxes, no shims; see `fidelity:` in `algorithm.yml`).

## Units
V-SHARP is a linear SMV deconvolution and scale-agnostic, so `recon.m` filters the ppm total field
directly; `localfield` is ppm.
