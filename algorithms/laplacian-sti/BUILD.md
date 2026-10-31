# Building laplacian-sti (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler, with the Image Processing
Toolbox**, and bake it onto the R2023b MATLAB Runtime. R2023b because it is the licensed MATLAB the
fidelity check runs on ([`../../fidelity/matlab/`](../../fidelity/matlab/README.md)), so the
container and the reference runs share one release. Same patterns as `../qsmart-matlab/BUILD.md`
(bundled NIfTI toolbox, OS gzip, no JVM, STI Suite `.p` code, no toolbox shims).

Stage: `field-mapping`. It consumes `phase` (radians, echoes on the 4th axis) and `params`, runs
`MRPhaseUnwrap` and STI Suite's echo combination, and writes `totalfield` (ppm).

## 1. Fetch build-time deps (not committed)
```bash
cp -r /path/to/NIfTI_20140122                          algorithms/laplacian-sti/nifti
cp -r /path/to/STISuite_V3.0/Core_Functions_P          algorithms/laplacian-sti/sti
```
`sti/` holds the STI Suite `.p` (real code) + `.m` (help-only stubs). Don't bundle
`Support_Functions/` wholesale — it contains a corrupt `wavelet_src/sfb3D_A.m` that breaks mcc's
parser, and `MRPhaseUnwrap` doesn't need it. [`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`)
is the same recipe as a script.

## 2. Compile
```bash
cd algorithms/laplacian-sti
matlab -batch "addpath('nifti'); addpath('sti'); \
  mcc('-m','recon.m','-a','sti','-o','recon','-d','.')"
```
`-a sti` force-bundles every `.p` (mcc can't trace dependencies **into** pcode, so it would
otherwise miss the helper `.p` that `MRPhaseUnwrap.p` calls at runtime). For the same reason,
`recon.m` names the Image Processing Toolbox functions the pcode calls in a `%#function` pragma
(`padarray`). They were found by profiling a licensed run (`fidelity/matlab/submit.sh laplacian-sti trace`).
Check that `unresolvedSymbols.txt` is empty and `requiredMCRProducts.txt` lists the Image
Processing Toolbox (35010). The harness does this compile as a Slurm job
(`submit.sh laplacian-sti build`) and keeps the log in `reports/build.txt`.

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/matlab-sti-laplacian:v1 .   # needs ./recon from §2
podman push  ghcr.io/astewartau/qsm-ci/matlab-sti-laplacian:v1
```
Make the package public (a new package starts private), pin `image:` in `algorithm.yml` by the pushed digest, and rerun the
fidelity check ([`fidelity/REPORT.md`](fidelity/REPORT.md)). The [`Dockerfile`](Dockerfile) is the
R2023b Runtime base (pinned by digest) plus `recon`; it sets `LD_LIBRARY_PATH`, which the r2023b
base doesn't. Never overwrite a tag.

## What recon.m does
As STI Suite 3.0's `QSM_GUI` ("3D GRE data"), probed headless in licensed MATLAB R2023b
(QSM.rs `src/unwrap/laplacian.rs`):
- `MRPhaseUnwrap(phase, 'voxelsize', vs)` once on all echoes, on the **raw, unmasked** wrapped
  phase, with its default `padsize` 12 (bitwise equal to an explicit `[12 12 12]`);
- the unwrapped echoes are **summed**, and the sum is used with `TE = ΣTE`: the field is
  `Σφₑ / ΣTEₑ` in rad/s, converted to ppm with 42.576 MHz/T (the QSM-CI contract's γ).

The field is written over the whole field of view; the mask is not used.

**Deviation: odd grids.** `MRPhaseUnwrap` needs an even grid. Probed in licensed R2023b, it errors
("Index in position 1 is invalid…") when the x or y extent is odd, and returns one slice too many
when z is odd. `recon.m` appends one zero slice to each odd axis, as `qsmart-matlab`'s `recon.m` pads
for STI Suite, and crops the result back. Even grids are untouched, so on an even acquisition this is
STI Suite's own output; the in-silico case (164×205×205) is padded to 164×206×206. In QSM.rs this is
`LaplacianSolver::Fft { pad: 12 }` with `laplacian_unmasked` and the `TEs` echo weighting, which
`laplacian-qsmrs`'s defaults (DCT solver, weighted average) are not, so the parity pair needs
matched settings.
