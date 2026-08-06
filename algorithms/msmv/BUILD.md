# Building mSMV (compiled MATLAB → MATLAB Runtime)

mSMV (Roberts et al., *Magn Reson Med* 2024, doi:10.1002/mrm.29963) as a QSM-CI `bfr`-stage submission.
Compile `recon.m` once on a machine with **MATLAB + MATLAB Compiler** (no license needed to *run* the
result on the free MATLAB Runtime). Proven pattern with R2026a.

Stage: `bfr` — consumes `totalfield` (ppm) + `mask` + `params`; produces `localfield` (ppm).

## What this submission does (standalone BFR vs refinement)

mSMV is fundamentally a **residual-shadow remover**: it filters the large-magnitude residual harmonic
background field near the brain boundary (maximum-value corollary of Green's theorem), preserving the
brain edge *without* mask erosion. In the paper/repo it is normally run as a **refinement after a
primary background-field removal** (PDF / VSHARP / LBV / SHARP).

The upstream `msmv()` function has a `prefilter` flag, though: with **prefilter=1 (its default)** it
**first** performs a Spherical-Mean-Value primary removal `RDF - SMV(RDF)` (radius `radius` mm) and
**then** the mSMV boundary correction. SMV is itself a complete harmonic background-field removal, so
`msmv(prefilter=1)` on a *total* field is a self-contained total→local BFR:

> **SMV primary removal  →  mSMV boundary shadow correction**

That is the composition this submission packages. `recon.m` calls the upstream function with the
prefilter defaulted on (we pass 8 positional args, so `prefilter` defaults to 1) and does **not**
prepend a separate BFR.

## Units

mSMV (like MEDI's `RDF`) works on the field in **radians**; its shadow-detection threshold is capped at
`0.01*B0/3` rad (`kernel_lim.m`). Our contract carries the field in **ppm**, so `recon.m` converts
`rad = ppm * 2π * gyro * B0 * TE` (gyro = 42.5774 MHz/T), runs mSMV, then converts back to ppm. mSMV is
(bar its thresholded steps) a linear high-pass filter, so the ppm output is scale-invariant in the
linear limit; `simulated_TE` (default 0.008 s) only sets the operating point of the radian threshold.

## Vessel mask

mSMV's optional vessel-protection step needs an **R2\*** map (via `fibermetric`), which the `bfr` stage
does not provide. Per the upstream README this step is skipped when R2\* is missing: `recon.m` passes an
all-zero R2\*, and the bundled `fibermetric` shim returns zeros → no voxels protected as vessels.

## Build-time deps (fetched, not committed — gitignored)

Only `recon.m`, `run.sh`, `algorithm.yml`, this file, and our own `shims/` live in git. The upstream
mSMV code (no license declared — academic use, cite the paper) is fetched at build time and baked into
the compiled binary, matching the WaveSep / chi-sep MATLAB submissions.

```bash
cd algorithms/msmv
git clone https://github.com/agr78/mSMV /tmp/mSMV
mkdir -p msmv_code
# mSMV core (the residual-shadow filter + adaptive kernel-limit threshold):
cp /tmp/mSMV/code/mSMV_functions/msmv.m        msmv_code/
cp /tmp/mSMV/code/mSMV_functions/kernel_lim.m  msmv_code/
# MEDI SMV helpers it depends on (Cornell MEDI toolbox, redistributed within mSMV/code/dependencies):
cp /tmp/mSMV/code/dependencies/MEDI_functions/SMV.m           msmv_code/
cp /tmp/mSMV/code/dependencies/MEDI_functions/sphere_kernel.m msmv_code/
cp /tmp/mSMV/code/dependencies/MEDI_functions/MaskErode.m     msmv_code/
```

`msmv.m` calls only `sphere_kernel`, `SMV`, `MaskErode`, `kernel_lim` (all above) plus `imbinarize` /
`fibermetric` — the latter two are Image Processing Toolbox and are replaced by our committed
`shims/` (see below), so **no IPT licence is needed at compile or run time**.

- `nifti/` — Jimmy Shen "Tools for NIfTI and ANALYZE" toolbox (as used by the other MATLAB
  submissions), e.g. `cp -r /path/to/NIfTI_20140122 algorithms/msmv/nifti`.

## Shims (committed — ours)

- `shims/imbinarize.m` — numeric-threshold binarization `I > t` (mSMV's only use), plus an Otsu
  fallback for the no-argument form.
- `shims/fibermetric.m` — returns zeros (vessel protection disabled; the `bfr` stage has no R2\*).

## Key patterns (shared with every MATLAB submission)

- **No Image Processing Toolbox at run time.** NIfTI I/O via the bundled toolbox
  (`load_untouch_nii`/`save_untouch_nii`) + OS `gunzip`/`gzip` for `.nii.gz` (the toolbox's own gzip
  needs the JVM, which compiled binaries lack). See `read_niigz`/`write_niigz` in `recon.m`.
- Runtime `addpath` of the vendored folders is guarded by `~isdeployed` (in the compiled binary the
  code is baked in and those folders don't exist on disk).

## 1. Compile

```bash
cd algorithms/msmv
matlab -batch "addpath('shims'); addpath('nifti'); addpath(genpath('msmv_code')); \
  mcc('-m','recon.m','-a','msmv_code','-a','shims','-a','nifti','-o','recon','-d','.')"
# -> ./recon (ELF binary)
```

`-a msmv_code -a shims -a nifti` force-bundle the vendored code onto the deployed path.

## 2. Bake the MCR image and push

```bash
docker build -t ghcr.io/astewartau/qsm-ci/msmv:v1 .   # FROM matlab-runtime:r2026a + COPY recon
docker push  ghcr.io/astewartau/qsm-ci/msmv:v1
```

Then **make the GHCR package public** (Package settings → Danger Zone → Change visibility → Public).
Point `algorithm.yml`'s `image:` at that tag. QSM-CI runs `/opt/qsm-ci/recon /input /output` on the
free Runtime, offline.

## 3. Score

mSMV is a classical CPU MATLAB filter (fast — no `ci_skip`, no special `runner`/`smoke_box` needed).
It scores on the canonical `bfr` datasets via `score.yml` once the image is public.

## Notes / status

- **Not yet compiled or scored** — `mcc` and `docker build` are deferred to Bunya/a human per the
  build policy (this box has no MATLAB Compiler + the IPT functions are not installed here, which is
  exactly why the shims exist). No scores are claimed.
- A future **QSM.rs (Rust) reimplementation** of mSMV is of interest (it is a classical filter). This
  submission packages the MATLAB original only.
