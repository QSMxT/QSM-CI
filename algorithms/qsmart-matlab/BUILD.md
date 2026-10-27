# Building qsmart-matlab (compiled MATLAB → MATLAB Runtime + ANTs N4)

Compile `recon.m` on a machine with **MATLAB + MATLAB Compiler R2023b**, and bake it onto the
R2023b MATLAB Runtime. R2023b because it is the licensed MATLAB the fidelity check
([`fidelity/`](fidelity/README.md)) runs on, so the container and the reference runs share one
release. Same patterns as
`../medi-cornell/BUILD.md` (bundled NIfTI toolbox, OS gzip, no JVM) and `../ilsqr-sti/BUILD.md`
(STI Suite `.p` code + IPT shims), plus the **QSMART v1.0 toolbox** and its Frangi/curvatures
dependencies with **build-time mex compilation**.

Stage: `end-to-end` — consumes `phase` (radians, 4-D) + `magnitude` + `mask` + `params`; runs the
full original QSMART.m pipeline (vasculature mask → Laplacian unwrap → echofit/R_0 → SDF stage 1
→ QSM_iLSQR → SDF stage 2 → QSM_iLSQR → adjust_offset) → `chimap` (ppm).

## 1. Fetch build-time deps (not committed; `shims/`, `recon.m`, `vasculature_mask_qsmci.m` ARE committed — ours)

```bash
cd algorithms/qsmart-matlab
QSMART=/path/to/QSMART                      # clone of github.com/wtsyeda/QSMART (no license file)
SUN=/path/to/sunhongfu-qsm                  # clone of github.com/sunhongfu/QSM (MIT)
STI=/path/to/STISuite_V3.0/STISuite_V3.0    # STI Suite v3 (Chunlei Liu; its own license)

# QSMART toolbox .m files actually used by recon.m (DICOM/coil-comb/BET files are skipped),
# plus Hongfu Sun's lapunwrap.m — unwrap_phase's 'laplacian' method calls it but the QSMART
# repo does not ship it (QSMART's makekspace.m/myisfield.m are its two helpers).
mkdir -p qsmart
cp "$QSMART"/QSMART_toolbox_v1.0/{unwrap_phase,echofit,QSMART_SDF,sdf_curvature,calculate_curvature,adjust_offset,makekspace,myisfield}.m qsmart/
cp "$SUN"/Misc/lapunwrap.m qsmart/

# Jimmy Shen NIfTI toolbox (QSMART bundles it under matlab-dependencies/)
cp -r "$QSMART"/matlab-dependencies/NIfTI_20140122 nifti

# Frangi vesselness filter + curvatures (File Exchange, bundled by QSMART). Drop the demo
# .mat volume so `-a frangi` doesn't bloat the binary (and *.mat is gitignored anyway).
cp -r "$QSMART"/matlab-dependencies/frangi_filter_version2a frangi
rm -f frangi/ExampleVolumeStent.mat
rm -f frangi/eig3volume.m     # 0-byte placeholder (mex-only function); mcc refuses empty .m files
# The QSMART copy of FrangiFilter3D.m carries a stray `keyboard` debug statement (line ~129, CRLF
# file) — a no-op in interactive/batch MATLAB but a FATAL "Debugging is not supported" error in
# deployed MCR mode. Comment it out (upstream Kroon code has no such line):
sed -i 's/^\( *\)keyboard\r*$/\1% keyboard  % QSM-CI: stray debug statement removed (fatal in deployed MCR mode)/' frangi/FrangiFilter3D.m
mkdir -p curvatures && cp "$QSMART"/matlab-dependencies/curvatures/{curvatures.m,license.txt} curvatures/

# STI Suite Core functions — QSMART's inversion IS STI Suite's QSM_iLSQR (obfuscated .p);
# it is not in the QSMART repo.
cp -r "$STI"/Core_Functions_P sti

# Robustness patch (same spirit as medi-cornell's store_CG_results stub): calculate_curvature.m
# does `scaledGC=GC./max(abs(GC(GC<0)))*curvConstant;` — on masks whose triangulated surface has
# NO concave points (GC<0 empty; happens on simulated phantom masks, verified on data/sim/dev)
# max() returns [] and the division errors. Guard the scale (no-op whenever negatives exist —
# with no negatives there is nothing the scale applies to):
perl -0pi -e 's/scaledGC=GC\.\/max\(abs\(GC\(GC<0\)\)\)\*curvConstant;/negGC=max(abs(GC(GC<0)));\nif isempty(negGC) || negGC==0, negGC=1; end % QSM-CI guard, see BUILD.md\nscaledGC=GC.\/negGC*curvConstant;/' qsmart/calculate_curvature.m
```

## 2. Compile the mex files (build time — the original ran `mex eig3volume.c` at RUN time)

```bash
matlab -batch "cd frangi; mex eig3volume.c"
# If mex reports "Supported compiler not detected" (a gcc newer than the release probes for),
# compile manually against the MATLAB headers — the resulting .mexa64 is what mcc bundles:
M=/path/to/MATLAB/R2023b
gcc -O2 -fPIC -shared -std=gnu99 -DMATLAB_MEX_FILE -I$M/extern/include \
    frangi/eig3volume.c -o frangi/eig3volume.mexa64 \
    -L$M/bin/glnxa64 -lmx -lmex -Wl,-rpath,$M/bin/glnxa64
```

`eig3volume` is mandatory (its `.m` is empty — mex-only). `imgaussian.c` is NOT built: it uses the
legacy 32-bit `int` dims mex API and no longer compiles against modern MATLAB; its `imgaussian.m`
fallback (running on the bundled `imfilter` shim) is used instead — same separable-Gaussian maths.
If a mex compile hits path issues on this box, remember to exclude any `eml` paths when adding
MATLAB paths (known quirk).

## 3. Compile recon

```bash
matlab -batch "addpath('shims','nifti','qsmart','frangi','curvatures','sti'); \
  mcc('-m','recon.m','-a','sti','-a','shims','-a','frangi','-o','recon','-d','.')"
```

`-a sti` force-bundles every `.p` (mcc can't trace into pcode); `-a shims` bundles the IPT/Stats
replacements; `-a frangi` bundles the mex binaries + Frangi `.m`s. `recon.m`'s own tracing pulls
in the qsmart/, nifti/ and curvatures/ functions it calls.

## Shims (`shims/`)

The MATLAB Runtime image is built without relying on the Image Processing or Statistics toolboxes,
so `shims/` replaces everything QSMART + STI Suite call from them. `shims/` is first on the path at
compile time, so the shims are what `mcc` bundles even when the build MATLAB has those toolboxes: `padarray`, `strel`/`imdilate`/`imerode`/`imclose`/
`imopen` (copied from `../ilsqr-sti/shims/` — QSM_iLSQR's `.p` need them too), plus new here:
`imbothat` (vessel enhancement), `graythresh` (Otsu on the Frangi map), `imgaussfilt3` (all SDF
proximity/filtering smoothing; supports per-axis sigma + 'FilterSize'), `imfilter` (imgaussian.m
fallback), and `prctile` (Stats; only QSMART's optional adaptive-threshold branches).

Checking the shims against the real toolboxes, and the built container against licensed MATLAB:
[`fidelity/README.md`](fidelity/README.md). Rerun it whenever a shim or the image changes.

## 4. Bake the image and push

```bash
podman build -t ghcr.io/astewartau/qsm-ci/matlab-qsmart:v2 .     # needs ./recon from §3
podman push  ghcr.io/astewartau/qsm-ci/matlab-qsmart:v2
```

Keep the package public, pin `image:` in `algorithm.yml` by the pushed digest, and rerun the
fidelity check. [`Dockerfile`](Dockerfile) is the usual MCR bake (`FROM
containers.mathworks.com/matlab-runtime:r2023b` + `COPY recon`) **plus ANTs
N4BiasFieldCorrection** (pinned release zip), which `vasculature_mask_qsmci.m` invokes on the
mean-echo magnitude exactly like the original toolbox did via `module load ants`. Without N4 on
PATH the code warns and proceeds uncorrected (fine for simulated, bias-free data only).

The Runtime's own libraries (its bundled `libcurl.so.4` and `libstdc++`) shadow the system ones,
so the Dockerfile clears `LD_LIBRARY_PATH` around the ANTs download, and installs
`N4BiasFieldCorrection` as a wrapper script that does the same (MATLAB's `system()` passes the
Runtime's `LD_LIBRARY_PATH` to child processes). The r2023b base doesn't set `LD_LIBRARY_PATH`
itself, so the Dockerfile sets it for the compiled binary.

Images: `v1` (R2026a Runtime, shims before the border fix, N4 output cast to double); `v2`
(R2023b, the fixed shims, N4 output kept single as the original;
the fidelity check passes, see `fidelity:` in `algorithm.yml`).

## Units

`phase` is radians; `echofit` fits phase/TE (rad/s) and divides by `params.ppm = gyro·B0/1e6`
→ `tfs` in ppm. `QSMART_SDF` multiplies back to rad/s and `QSM_iLSQR` is called with
`'TE',1000,'B0',B0` (the Hongfu-Sun convention: rad/s treated as radians at TE = 1 s), which
undoes the same `gyro·B0` factor → chi in ppm. `adjust_offset` combines both stages in ppm.
`chimap.nii.gz` is written through the input mask's untouched header (affine preserved).
