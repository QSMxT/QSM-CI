# Building lbv-cornell (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler** and bake it onto the R2023b
MATLAB Runtime, as `../pdf-cornell/BUILD.md`. The method is the authors' `LBV.m` and its C++
full-multigrid solver `mexMGv6` (Dong Zhou), from the Cornell **MEDI toolbox 2024.11.26**.

Stage: `bfr`. It consumes `totalfield` (ppm), `mask` and `params`, runs `LBV.m` and writes
`localfield` (ppm) as LBV.m returns it: defined on LBV's interior (the mask minus its boundary
layer), and 0 elsewhere except where mexMGv6's prolongation wrote into the boundary layer and a
few voxels just outside the mask (about 1–2 % of the field's norm inside the mask).

## 1. Fetch build-time deps (not committed)
```bash
cd algorithms/lbv-cornell
cp -r /path/to/NIfTI_20140122 nifti
mkdir -p medi && cp /path/to/MEDI_toolbox-2024.11.26/functions/_LBV/{LBV.m,mexMGv6.cpp} medi/
```
The toolbox also ships `mexMGv6.mexa64`, but that binary predates its source: it returns one output,
and `LBV.m` asks for two (`[tmp, interior] = mexMGv6(...)`: "One or more output arguments not
assigned"). So the mex is compiled from the shipped `mexMGv6.cpp`, which does return `interior`.
[`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`, `fid_build_hook`) is the same recipe as
a script.

## 2. Compile
```bash
matlab -batch "cd medi; mex mexMGv6.cpp"
matlab -batch "addpath('nifti'); addpath('medi'); mcc('-m','recon.m','-a','medi/mexMGv6.mexa64','-o','recon','-d','.')"
```
`mex` builds with R2023b's default C++ compiler on the build node; the licensed runs compile the same
source the same way. `-a` makes sure the mex is bundled. Check that `unresolvedSymbols.txt` and `mccExcludedFiles.log`
list nothing (`submit.sh lbv-cornell build` does this as a Slurm job).

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/matlab-medi:lbv-v1 .
podman push  ghcr.io/astewartau/qsm-ci/matlab-medi:lbv-v1
```
The image is a tag of the public `matlab-medi` package. Pin `image:` by the pushed digest and rerun
the fidelity check. Never overwrite a tag.

## Defaults and units
`LBV.m`'s own defaults: `tol` 0.01, `depth` −1 (automatic: `log2` of the smallest dimension minus 3),
`peel` 0, and 30/100/100 relaxations (`LBV.m:29-46`). MEDI's pipeline script has LBV as a commented
alternative to PDF (`README.m:129`) and passes `tol` 0.005 there; set `tol` to 0.005 for that call.

`mexMGv6` stops its coarsest-grid relaxation when the update falls below `tol` in absolute terms
(`MG::relax`), so the result depends on the field's scale. `recon.m` gives LBV the field in MEDI's
units, as `README.m` does: radians accumulated over the echo spacing, `field·1e-6·2π·CF·delta_TE`
(`CF` = 42.576 MHz/T · `B0`, `delta_TE` = `TE(2) − TE(1)`), and converts the result back to ppm.
The solver computes in single precision.

With `peel` > 0, mexMGv6 writes the peeled mask to `mask_p<peel>.bin` in the working directory
(`MG::preProcessing`); where it cannot (the image's working directory is read-only) it closes a
NULL `FILE*` and MATLAB dies with a segmentation fault. Run the image with a writable working
directory (e.g. `-w /tmp`) for `peel` > 0.

QSM.rs's LBV (`src/bgremove/lbv.rs`) is a port of this solver (astewartau/QSM.rs#406): its
single precision is bit-identical to this mex, and its default double precision differs by
rounding.
