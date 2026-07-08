# Building matlab-sti-star (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` on a machine with **MATLAB + MATLAB Compiler** (R2026a). Same patterns as
`../matlab-tkd/BUILD.md` (bundled NIfTI toolbox, OS gzip, no JVM), plus **STI Suite v3** (obfuscated
`.p` functions) and a small **Image Processing Toolbox shim set** (the MATLAB Runtime does **not**
include IPT, and STI Suite's `.p` call `padarray` + morphology).

Stage: `dipole` — consumes `localfield` (ppm) + `mask` + `params`; runs `QSM_star` → `chimap` (ppm).
Validated corr **0.992**, NRMSE 0.30 vs GT on `data/sim/dev`.

## 1. Fetch build-time deps (not committed; `shims/` IS committed — it's ours)
```bash
cp -r /path/to/NIfTI_20140122                          algorithms/matlab-sti-star/nifti
cp -r /path/to/STISuite_V3.0/Core_Functions_P          algorithms/matlab-sti-star/sti
```
`sti/` holds the STI Suite `.p` (real code) + `.m` (help-only stubs). Don't bundle
`Support_Functions/` wholesale — it contains a corrupt `wavelet_src/sfb3D_A.m` that breaks mcc's
parser, and STAR-QSM doesn't need it.

## 2. Compile
```bash
cd algorithms/matlab-sti-star
matlab -batch "addpath('shims'); addpath('nifti'); addpath('sti'); \
  mcc('-m','recon.m','-a','sti','-a','shims','-o','recon','-d','.')"
```
`-a sti` force-bundles every `.p` (mcc can't trace dependencies **into** obfuscated pcode, so it
would otherwise miss the helper `.p` that `QSM_star.p` calls at runtime). `-a shims` bundles the
IPT replacements so they're on the deployed path.

## IPT shims (`shims/`)
The MATLAB Runtime has no Image Processing Toolbox, so these replace the IPT functions STI Suite's
`.p` invoke: `padarray` (zero-pad), and greyscale/binary morphology `strel`/`imdilate`/`imerode`/
`imclose`/`imopen`. `QSM_star`→`FastQSM` uses `imclose` with a 1×3 line element; the morphology
shims handle arbitrary neighbourhoods (row/column/3-D). If a future STI method needs another IPT
function, add a shim here.

## 3. Bake the MCR image and push
```bash
docker build -t ghcr.io/astewartau/qsm-ci/matlab-sti-star:v1 .   # FROM matlab-runtime:r2026a + COPY recon
docker push  ghcr.io/astewartau/qsm-ci/matlab-sti-star:v1
```
Then make the GHCR package public.

## Units
`localfield` is ppm; STI Suite works in radians. recon.m builds `TissuePhase = field·1e-6·2π·γ·B0·TE`
(γ = 42.576e6) and passes `TE`,`B0` so `QSM_star` undoes the same scaling → chi in ppm; the exact TE
cancels.
