# Building amp-pe (compiled MATLAB → MATLAB Runtime)

AMP-PE (Huang et al., *Magn Reson Med* 2023) as a QSM-CI `dipole`-stage submission. Compile
`recon.m` once on a machine with **MATLAB + MATLAB Compiler + Wavelet Toolbox** (no license needed
to *run* the result on the free MATLAB Runtime). Proven with R2026a.

## What this submission does
The upstream [QSM_AMP_PE](https://github.com/EmoryCN2L/QSM_AMP_PE) pipeline goes from raw multi-echo
phase all the way to χ (unwrap → BET → PDF background removal → AMP-PE inversion). For the `dipole`
stage the **local field is already provided**, so `recon.m` keeps only the AMP-PE inversion: it turns
the local field (ppm) into a simulated single-echo phase (radians) and runs the two-step AMP-PE
solve (preliminary single-Gaussian noise model → final Gaussian-mixture model), mirroring the
"combined" path of `qsm_multi_echo_combined.m`. Magnitude (optional) is used as the data-fidelity
weight and to build the wavelet morphology mask.

## Build-time dependencies (fetched, not committed — gitignored)
Only `recon.m`, `run.sh`, `algorithm.yml` and this file live in git. The upstream code below is fetched
at build time and baked into the compiled binary, matching the other MATLAB submissions:

- `amp_pe_qsm/` + `functions/` — the AMP-PE solver + inversion helpers, from
  [EmoryCN2L/QSM_AMP_PE](https://github.com/EmoryCN2L/QSM_AMP_PE) (**MIT**), pinned at commit
  `15bf8dc`. Only these are needed (the unwrap/BET/PDF/erosion helpers are skipped by this stage):
  ```bash
  cd algorithms/amp-pe
  git clone https://github.com/EmoryCN2L/QSM_AMP_PE /tmp/QSM_AMP_PE
  git -C /tmp/QSM_AMP_PE checkout 15bf8dc
  cp -r /tmp/QSM_AMP_PE/amp_pe_qsm .
  mkdir -p functions
  cp /tmp/QSM_AMP_PE/functions/GenerateDipoleFT3Drot.m /tmp/QSM_AMP_PE/functions/SI_operator_withmask.m functions/
  cp /tmp/QSM_AMP_PE/functions/PDF_imp/fftnc.m /tmp/QSM_AMP_PE/functions/PDF_imp/ifftnc.m functions/
  cp /tmp/QSM_AMP_PE/functions/from_FANSI/dipole_kernel_angulated.m /tmp/QSM_AMP_PE/functions/from_FANSI/chiL2.m functions/
  ```
- `nifti/` — Jimmy Shen "Tools for NIfTI and ANALYZE" toolbox (as used by the other MATLAB
  submissions), e.g. `cp -r /path/to/NIfTI_20140122 algorithms/amp-pe/nifti`.

## Key patterns (shared with every MATLAB submission)
- **No Image Processing Toolbox.** NIfTI I/O via the bundled toolbox (`load_untouch_nii`/
  `save_untouch_nii`), plus OS `gunzip`/`gzip` for `.nii.gz` (the toolbox's own gzip needs the JVM,
  which compiled binaries lack). See `read_niigz`/`write_niigz` in `recon.m`.
- **Wavelet Toolbox is required at compile time** (db1/db2 `wavedec3`/`waverec3`); `mcc` bundles the
  toolbox code into the binary, so the run-time Runtime image needs no Wavelet licence.
- `dwtmode('per','nodisp')` — the 2nd arg suppresses a status message that otherwise triggers a
  message-catalog lookup.
- Runtime `addpath` of the vendored folders is guarded by `~isdeployed` (in the compiled binary the
  code is baked in and those folders don't exist on disk).

## 1. Compile
```bash
cd algorithms/amp-pe
# Wavelet Toolbox must be on the path. If it lives outside matlabroot, add it (excluding the
# codegen 'eml' folders, whose qmf.m shadows the runtime one):
WAV=/path/to/toolbox/wavelet   # e.g. .../toolbox/wavelet if outside matlabroot
matlab -batch "\
  p=genpath('$WAV'); parts=strsplit(p,pathsep); \
  parts=parts(~cellfun(@(s) contains(s,[filesep 'eml'])||isempty(s),parts)); addpath(strjoin(parts,pathsep)); \
  addpath('nifti'); addpath('functions'); addpath(genpath('amp_pe_qsm')); \
  mcc('-m','recon.m','-o','recon','-d','.','-a','./nifti','-a','./functions','-a','./amp_pe_qsm', \
      '-a','$WAV/core/wavelet/dbwavf.m')"
# -> ./recon (ELF binary, ~750 KB)
```

`-a dbwavf.m` is required: `wfilters` builds the Daubechies filter name and calls it with a dynamic
`feval`, which `mcc`'s dependency analysis can't follow, so `dbwavf` must be force-included. Every
other wavelet function on the db1/db2 path (`wavedec3`, `waverec3`, `wfilters`, `orthfilt`, …) is
detected automatically. (If you switch to a non-Daubechies basis, add that family's `*wavf.m` too.)

## 2. Bake the MCR image and push
```bash
docker build -t ghcr.io/astewartau/qsm-ci/amp-pe:v1 .   # FROM matlab-runtime:r2026a + COPY recon
docker push  ghcr.io/astewartau/qsm-ci/amp-pe:v1
```
Point `algorithm.yml`'s `image:` at that tag and make the package public. QSM-CI runs
`/opt/qsm-ci/recon /input /output` on the free Runtime, offline.

## Notes
- Runtime on the 96×96×60 dev volume: ~5.5 min at the default 25+25 linearization iterations
  (single-threaded-ish); well within the 2 h limit. Reduce `max_linearization_ite` to trade quality
  for speed.
- AMP-PE returns a near-zero-mean χ within the mask (the constant offset is unresolvable from the
  local field alone); the detrended metrics are the fair comparison.
