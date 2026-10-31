# Building iharperella-sti (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler, with the Image Processing
Toolbox**, and bake it onto the R2023b MATLAB Runtime. R2023b because it is the licensed MATLAB the
fidelity check runs on ([`../../fidelity/matlab/`](../../fidelity/matlab/README.md)), so the
container and the reference runs share one release. Same patterns as `../qsmart-matlab/BUILD.md`
(bundled NIfTI toolbox, OS gzip, no JVM, STI Suite `.p` code, no toolbox shims).

Stage: `bfr`. It consumes `totalfield` (ppm), `mask` and `params`, runs `iHARPERELLA` and writes
`localfield` (ppm), 0 outside the mask.

## 1. Fetch build-time deps (not committed)
```bash
cp -r /path/to/NIfTI_20140122                          algorithms/iharperella-sti/nifti
cp -r /path/to/STISuite_V3.0/Core_Functions_P          algorithms/iharperella-sti/sti
```
`sti/` holds the STI Suite `.p` (real code) + `.m` (help-only stubs). Don't bundle
`Support_Functions/` wholesale — it contains a corrupt `wavelet_src/sfb3D_A.m` that breaks mcc's
parser, and `iHARPERELLA` doesn't need it. [`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`)
is the same recipe as a script.

## 2. Compile
```bash
cd algorithms/iharperella-sti
matlab -batch "addpath('nifti'); addpath('sti'); \
  mcc('-m','recon.m','-a','sti','-o','recon','-d','.')"
```
`-a sti` force-bundles every `.p` (mcc can't trace dependencies **into** pcode, so it would
otherwise miss the helper `.p` that `iHARPERELLA.p` calls at runtime). For the same reason,
`recon.m` names the Image Processing Toolbox functions the pcode calls in a `%#function` pragma
(`padarray`). They were found by profiling a licensed run (`fidelity/matlab/submit.sh iharperella-sti trace`).
Check that `unresolvedSymbols.txt` is empty and `requiredMCRProducts.txt` lists the Image
Processing Toolbox (35010). The harness does this compile as a Slurm job
(`submit.sh iharperella-sti build`) and keeps the log in `reports/build.txt`.

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/matlab-sti-iharperella:v2 .   # needs ./recon from §2
podman push  ghcr.io/astewartau/qsm-ci/matlab-sti-iharperella:v2
```
The package is public (its `v1` was QSM-CI's earlier build, removed in #137 as broken), pin `image:` in `algorithm.yml` by the pushed digest, and rerun the
fidelity check ([`fidelity/REPORT.md`](fidelity/REPORT.md)). The [`Dockerfile`](Dockerfile) is the
R2023b Runtime base (pinned by digest) plus `recon`; it sets `LD_LIBRARY_PATH`, which the r2023b
base doesn't. Never overwrite a tag.

## Input, defaults and units
STI Suite's help text and `STI_Templates.m` call `iHARPERELLA` on the "raw phase", but probed in
licensed MATLAB R2023b, STI Suite 3.0's `iHARPERELLA` does not unwrap: it takes the spectral
Laplacian of its input as it is (on a synthetic head whose phase wraps in 59 % of the brain, its
output from the wrapped phase correlates −0.03 with the true local phase, from the unwrapped phase
0.98; QSM.rs `src/bgremove/iharperella.rs`). So it takes the `bfr` stage's unwrapped total field,
as QSM.rs's port does.

Defaults are the function's: `niter` 40, `padsize` 0 (probed: bitwise equal to `[0 0 0]`, while
`STI_Templates.m` lists `[12 12 12]`). The Laplacian and the LSQR solve are linear, with a relative
tolerance, so `recon.m` gives it the ppm field directly; `localfield` is ppm.

Images: `v1` (an earlier build on the raw phase, removed in #137); `v2` (R2023b, the real
toolboxes, the total field; see `fidelity:` in `algorithm.yml`).
