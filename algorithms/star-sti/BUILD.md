# Building star-sti (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler, with the Image Processing
Toolbox**, and bake it onto the R2023b MATLAB Runtime. R2023b because it is the licensed MATLAB the
fidelity check runs on ([`../../fidelity/matlab/`](../../fidelity/matlab/README.md)), so the
container and the reference runs share one release. Same patterns as `../qsmart-matlab/BUILD.md`
(bundled NIfTI toolbox, OS gzip, no JVM, STI Suite `.p` code, no toolbox shims).

Stage: `dipole` — consumes `localfield` (ppm) + `mask` + `params`; runs `QSM_star` → `chimap` (ppm).

## 1. Fetch build-time deps (not committed)
```bash
cp -r /path/to/NIfTI_20140122                          algorithms/star-sti/nifti
cp -r /path/to/STISuite_V3.0/Core_Functions_P          algorithms/star-sti/sti
cp -r /path/to/STISuite_V3.0/Support_Functions/qsm_kiwi_1 algorithms/star-sti/kiwi
mkdir -p algorithms/star-sti/sparsa
find /path/to/STISuite_V3.0/Support_Functions/SpaRSA -maxdepth 1 -name '*.m' ! -name 'demo_*' \
    -exec cp {} algorithms/star-sti/sparsa/ \;
```
`QSM_star` builds its operators from the classes in `Support_Functions/qsm_kiwi_1` (`@iFDF`,
`@suscepMap`, `@TVOP_3Dnew`), and its `SpaRSA_HW` solver calls `soft` from `Support_Functions/SpaRSA`.
Neither is in `Core_Functions_P`.
`sti/` holds the STI Suite `.p` (real code) + `.m` (help-only stubs). Don't bundle
`Support_Functions/` wholesale — it contains a corrupt `wavelet_src/sfb3D_A.m` that breaks mcc's
parser, and QSM_star needs only two of its folders (below). [`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`)
is the same recipe as a script.

## 2. Compile
```bash
cd algorithms/star-sti
matlab -batch "addpath('nifti'); addpath('sti'); addpath('kiwi'); addpath('sparsa'); \
  mcc('-m','recon.m','-a','sti','-a','kiwi','-a','sparsa','-o','recon','-d','.')"
```
`-a sti -a kiwi -a sparsa` force-bundle every `.p` and the classes (mcc can't trace dependencies **into** pcode, so it would
otherwise miss the helper `.p` and classes that `QSM_star.p` calls at runtime). For the same reason,
`recon.m` names the Image Processing Toolbox functions the pcode calls in a `%#function` pragma
(`padarray`). They were found by profiling a licensed run (`fidelity/matlab/submit.sh star-sti trace`).
Check that `unresolvedSymbols.txt` is empty and `requiredMCRProducts.txt` lists the Image
Processing Toolbox (35010). The harness does this compile as a Slurm job
(`submit.sh star-sti build`) and keeps the log in `reports/build.txt`.

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/matlab-sti-star:v2 .   # needs ./recon from §2
podman push  ghcr.io/astewartau/qsm-ci/matlab-sti-star:v2
```
Keep the package public, pin `image:` in `algorithm.yml` by the pushed digest, and rerun the
fidelity check ([`fidelity/REPORT.md`](fidelity/REPORT.md)). The [`Dockerfile`](Dockerfile) is the
R2023b Runtime base (pinned by digest) plus `recon`; it sets `LD_LIBRARY_PATH`, which the r2023b
base doesn't.

Images: `v1` (R2026a Runtime, toolbox shims whose greyscale `imdilate`/`imerode` wrapped round at
the volume border; its Dockerfile was `FROM matlab-runtime:r2026a` + `COPY recon` + `chmod +x`);
`v2` (R2023b, the real toolboxes, no shims; see `fidelity:` in `algorithm.yml`).

## Units
`localfield` is ppm; STI Suite works in radians. recon.m builds `TissuePhase = field·1e-6·2π·γ·B0·TE`
(γ = 42.576e6) and passes `TE`,`B0` so `QSM_star` undoes the same scaling → chi in ppm; the exact TE
cancels.
