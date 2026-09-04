# APART-QSM — vendor, compile, image, score (deferred Bunya steps)

APART-QSM is a GRE-based (signal-domain) iterative source-separation method (Li/Wang et al.,
*NeuroImage* 274:120148, 2023; https://github.com/AMRI-Lab/APART-QSM). Its core alternates a
voxel-wise magnitude-decay ("a-map") fit with a TV-regularised χ+/χ− dipole inversion. Like DECOMPOSE
it's a **per-voxel iterative** method, so its test/`mcc` build run where the toolboxes are (Bunya), and
the first job is to **measure the runtime** before committing it to the leaderboard.

## 0. BLOCKER — the public repo does NOT ship the core solver (READ FIRST)
The published repo (commit `c49bad4`) contains ONLY:
- `single_orientation/APART_QSM_single_ori_demo.m` and `multi_orientation/APART_QSM_multi_ori_demo.m`
- helpers `dipole_kernel.m`, `gradient_mask_all.m`, the `@TVOP` finite-difference class
- `.mat` test data.

The actual solver **`apart_qsm_single_ori` (and `apart_qsm_multi_ori`) is NOT distributed** — the demos
call it but the function file is absent from the repo (verified across the full git history). The
vendored helpers alone cannot separate χ+/χ−. **Do not compile, image, or score until the core solver
is obtained**, because there is nothing to compile against yet.

To unblock, obtain `apart_qsm_single_ori.m` (and any private helpers it needs) from the authors
(AMRI-Lab / Hongjiang Wei, SJTU) — e.g. open an issue on the repo or email — then either:
- place it under `algorithms/apart-qsm/apart_core/` and add `-a apart_core` at `mcc` time, or
- point `$APART_CORE` at it for an uncompiled local run.

`recon.m` is authored to the **published demo call convention**:
`Res_map = apart_qsm_single_ori(mag_img, phi_local_img, r2_img, chi_img, params)` with
`Res_map(:,:,:,1)=X_para (χ+, ppm)`, `Res_map(:,:,:,2)=X_dia_abs (|χ−|, ppm)`. If the obtained solver's
signature or `params` fields differ, adjust `recon.m` accordingly before compiling.

## What this submission consumes / produces
Stage `chi-separation` — declares `inputs: [magnitude, localfield, r2prime, chimap, mask, params]`
(a subset of the stage's `consumes`; no raw `phase` needed). Produces `chi-para` (χ+) + `chi-dia`
(χ−, positive magnitude). Adaptation vs. the reference demo:
- The demo takes **per-echo local phase** `phi_local_img`. The stage provides a single 3D local field
  (`localfield.nii.gz`, ppm); `recon.m` synthesises the per-echo local phase from it
  (`phi = localfield·1e-6·γ·B0·TE`, χ being echo-independent), so no raw phase / in-house
  unwrap+BFR+QSM is required and APART's separation step is isolated from upstream error.
- The demo's `chi_img` is an initial STAR-QSM; we pass the provided χ_total (`chimap.nii.gz`).
- The demo's `r2_img` is passed as the provided `r2prime.nii.gz` (Hz). If the obtained solver expects
  R2 (total) rather than R2′, revisit this — the chisep phantom only provides R2′.
- Magnitude-decay kernel `params.a` defaults to the phantom's `Dr = 137 Hz/ppm`
  (data/README.md), not the demo's 3T value of 323.5.

## Vendored deps (committed here)
- `apart_utils/` — the repo's published single-orientation helpers: `dipole_kernel.m`,
  `gradient_mask_all.m`, `@TVOP/`. (No LICENSE in the repo — academic use, cite the paper.)
- `nifti/` — Jimmy Shen NIfTI toolbox (`make_nii`/`save_nii`/`load_untouch_nii`), same as amp-pe.
- **NOT committed (see §0):** `apart_core/` — the author-obtained solver `apart_qsm_single_ori.m`.

## 1. Feasibility / speed test (once the core is in place)
```bash
module load matlab/R2023b
export APART_CORE=.../apart-qsm/apart_core          # the author-obtained solver
matlab -batch "addpath('algorithms/apart-qsm'); recon('data/sim/chisep/inputs','/tmp/apart_out')"
```
Time it on the full brain. If within a self-hosted score job's cap (e.g. 360 min, many cores), proceed;
otherwise consider a `smoke_box`-only leaderboard entry or reduced iterations (changes results).
Sanity-score the crop against GT:
```bash
python eval/qsm_eval.py --kind chisep --component para --recon /tmp/apart_out/chi-para.nii.gz \
  --truth data/sim/chisep/groundtruth/chi-para.nii.gz --seg .../dseg.nii.gz --mask .../mask.nii.gz
```

## 2. Compile + image
```bash
cd algorithms/apart-qsm
matlab -batch "addpath('nifti'); addpath('apart_utils'); addpath('apart_core'); \
  mcc('-m','recon.m','-a','nifti','-a','apart_utils','-a','apart_core','-o','recon','-d','.')"
docker build -t ghcr.io/astewartau/qsm-ci/apart-qsm:v1 .   # FROM matlab-runtime:r2023b + COPY recon
docker push  ghcr.io/astewartau/qsm-ci/apart-qsm:v1        # then make the GHCR package public
```
`mcc` needs the **Optimization Toolbox** present at compile (the a-map / dipole fits use it, as in the
DECOMPOSE build); confirm from the obtained solver whether it also uses the **Image Processing Toolbox**
(morphology) — if so, either module-load it at compile or add IPT/SPT shims like `chi-sep-medi/shims/`.
Compile on R2023b so the runtime base in the Dockerfile matches.

## 3. Score on the chisep phantom
Routed via `score.yml` on the canonical chisep phantom (χ+ and χ− scored against GT). `runner:
self-hosted` + `smoke_box: 24` (PR --smoke gate fits only a 24³ central box; the full score run is
unaffected).

## Blockers / open items
- **Missing core solver** (§0) — top blocker; nothing runs until it's obtained.
- **R2 vs R2′** — confirm whether the solver's third argument is R2 (total) or R2′; the phantom provides
  R2′ only.
- **echoes / B0** — the phantom has 4 echoes at 7T; the demo used 6 echoes at 3T. Watch fit quality and
  whether the a-map default needs re-tuning for 7T.
- Held out of any PR until §0 is resolved and the feasibility run passes.
