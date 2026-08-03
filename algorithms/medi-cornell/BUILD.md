# Building matlab-medi (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` on a machine with **MATLAB + MATLAB Compiler** (R2026a). The result runs
license-free on the MATLAB Runtime. Same patterns as `matlab-tkd` (bundled NIfTI toolbox, OS
gzip; see `../matlab-tkd/BUILD.md`), plus the Cornell **MEDI toolbox**.

Stage: `bfr+dipole` — consumes `totalfield` (ppm), `magnitude`, `mask`, `params`; PDF background
removal → `MEDI_L1` → `chimap` (ppm).

## 1. Fetch build-time deps (not committed)
```bash
cp -r /path/to/NIfTI_20140122               algorithms/matlab-medi/nifti   # Jimmy Shen toolbox
cp -r /path/to/MEDI_toolbox/functions       algorithms/matlab-medi/medi    # Cornell MEDI toolbox
# store_CG_results is only referenced by an unused MEDI_L1 debug branch — add a no-op stub so mcc resolves it:
printf 'function store_CG_results(varargin)\nend\n' > algorithms/matlab-medi/medi/store_CG_results.m
```

## 2. Compile
```bash
cd algorithms/matlab-medi
matlab -batch "addpath('nifti'); addpath('medi'); mcc('-m','recon.m','-o','recon','-d','.')"   # -> ./recon
```
mcc traces only the MEDI functions `recon.m` actually calls (PDF, MEDI_L1 and their deps); the
DICOM/bet2/GUI files in `medi/` are ignored.

## 3. Bake the MCR image and push
```bash
docker build -t ghcr.io/astewartau/qsm-ci/matlab-medi:v1 .   # FROM matlab-runtime:r2026a + COPY recon
docker push  ghcr.io/astewartau/qsm-ci/matlab-medi:v1
```
Then make the GHCR package public.

## Units
`totalfield` is ppm; MEDI works in radians. recon.m converts `iFreq = field·1e-6·2π·CF·delta_TE`
(CF = 42.576e6·B0) and MEDI_L1 converts back to ppm via `/(2π·delta_TE·CF)·1e6`, so the
`delta_TE·CF` factor cancels and the chi output is ppm regardless of the exact `delta_TE` — real
values are used so the default `lambda` stays well-scaled.
