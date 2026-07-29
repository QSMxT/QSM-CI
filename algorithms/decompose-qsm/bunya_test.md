# DECOMPOSE-QSM — feasibility + build on Bunya

DECOMPOSE's core is `lsqcurvefit` (**Optimization Toolbox**), which the local MATLAB doesn't have — so
its test and `mcc` build must run where the toolbox is (Bunya). It's also a **per-voxel non-linear
fit** (30 `lsqcurvefit` solves × ~2M brain voxels), so the first job is to **measure the runtime**
before committing it to the leaderboard.

## Toolboxes needed (env vars, as in the iLSQR diagnostic)
- `CHISEP_TOOLBOX` → chi-separation toolbox (`Preprocessing4Phase`)
- `CHISEP_STISUITE` → STI Suite v3 (`MRPhaseUnwrap`, `V_SHARP`, `QSM_star`)
- `DECOMPOSE_UTILS` → `algorithms/decompose-qsm/decompose_utils/`
- `CHISEP_NIFTI` → Jimmy Shen NIfTI toolbox
- Optimization Toolbox (module-loaded MATLAB on Bunya has it)

## 1. Feasibility / speed test (a central crop, then extrapolate)
```bash
module load matlab/R2023b
export CHISEP_TOOLBOX=.../Chisep_Toolbox_v1.1.3
export CHISEP_STISUITE=.../STISuite_V3.0/STISuite_V3.0
export DECOMPOSE_UTILS=.../algorithms/decompose-qsm/decompose_utils
export CHISEP_NIFTI=.../algorithms/matlab-tkd/nifti
export DECOMPOSE_CROPBOX=24     # fit only a 24^3 central box; prints "fitting N voxels" + "fit done in T s"
matlab -batch "addpath('algorithms/decompose-qsm'); recon('data/sim/chisep/inputs','/tmp/decompose_out')"
```
- Read the printed **voxels fitted** and **fit time**, divide to get per-voxel time, multiply by the full
  brain-voxel count (÷ cores) → the full-brain runtime estimate. If that's within a dedicated score job's
  cap (e.g. self-hosted 360 min with many cores), proceed; otherwise it's not leaderboard-viable as-is
  (consider fewer `DECOMPOSE_NINNER`, or a coarser grid — both change results).
- Score the crop against GT to sanity-check the separation:
  `python eval/qsm_eval.py --kind chisep --component para --recon /tmp/decompose_out/chi-para.nii.gz
   --truth data/sim/chisep/groundtruth/chi-para.nii.gz --seg .../dseg.nii.gz --mask .../mask.nii.gz`.

## 2. Full run (only if the estimate is acceptable)
Drop `DECOMPOSE_CROPBOX` (fit the whole brain) and confirm χ+/χ− scores.

## 3. Compile + image (like chi-sep-ilsqr/BUILD.md)
```bash
cd algorithms/decompose-qsm
matlab -batch "addpath('decompose_utils'); addpath('nifti'); addpath('sti'); addpath(genpath('chisep')); \
  mcc('-m','recon.m','-a','sti','-a','chisep','-a','decompose_utils','-o','recon','-d','.')"
docker build -t ghcr.io/astewartau/qsm-ci/decompose-qsm:v1 .   # FROM matlab-runtime:r2026a + COPY recon
docker push  ghcr.io/astewartau/qsm-ci/decompose-qsm:v1        # then make the package public
```
mcc needs the Optimization Toolbox present at compile so `lsqcurvefit` bundles into the binary.

## Blockers / open items
- **phase input**: DECOMPOSE consumes multi-echo `phase.nii.gz` (+ magnitude), which the chi-separation
  **stage** doesn't yet expose. Add `phase` to `STAGES["chi-separation"]["consumes"]` (qsm_ci/stages.py)
  and ensure the scored chisep dataset (OSF) includes phase.nii.gz. Our local phantom already has it.
- **echoes**: the phantom has 4 echoes; the method's demo used 8. A 6-parameter-per-voxel fit from 4
  complex points is marginal — watch the fit quality.
- Held out of any PR until the feasibility run passes.
