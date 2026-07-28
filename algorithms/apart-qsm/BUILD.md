# APART-QSM — build & publish the environment image (human step)

MATLAB method. The environment image has **not** been built or pushed. This scaffold documents the
build path and the single biggest blocker.

## 0. BLOCKER — the core solver is not in the public repo

The public repo <https://github.com/AMRI-Lab/APART-QSM> ships only:

```
single_orientation/APART_QSM_single_ori_demo.m   # the demo (calls apart_qsm_single_ori)
single_orientation/dipole_kernel.m
single_orientation/gradient_mask_all.m
single_orientation/@TVOP/ ...                     # finite-difference operator class
single_orientation/single_orientation_data/*.mat # demo data
multi_orientation/ ...                            # multi-orientation counterpart
```

The function the demo actually calls — **`apart_qsm_single_ori.m`** (and the multi-ori
`apart_qsm_multi_ori.m`) — is **NOT present**. `recon.m` is written to the exact contract inferred
from the demo, but it will `Undefined function 'apart_qsm_single_ori'` until that solver is obtained.

**Action:** email the authors (AMRI-Lab / Hongjiang Wei) or open a GitHub issue requesting the solver;
also `save_nii`/`make_nii` (Jimmy Shen NIfTI) are used by the demo but not vendored. Place the solver +
its private deps into the `single_orientation/` folder that `$APART_HOME` points at, then `genpath`
picks it up. Do not proceed to build the image before this exists.

## 1. Inputs the solver expects (contract)

From `APART_QSM_single_ori_demo.m`:

```matlab
Res_map = apart_qsm_single_ori(mag_img, phi_local_img, r2_img, chi_img, params);
```

| arg             | shape            | units / meaning                                              |
|-----------------|------------------|-------------------------------------------------------------|
| `mag_img`       | (x,y,z,echo)     | magnitude, arbitrary units                                  |
| `phi_local_img` | (x,y,z,echo)     | **local** (background-removed) phase, radians               |
| `r2_img`        | (x,y,z)          | **R2** map, s⁻¹ (monoexponential magnitude decay; NOT R2\*) |
| `chi_img`       | (x,y,z)          | initial QSM (χ_total), ppm (demo seeds with STAR-QSM)       |
| `params`        | struct           | mask, size, voxel_size(mm), n_echo, TEs(s), gamma(MHz/T), B0(T), B0_dir, a(Hz/ppm), tol_a, lambda_r2prime, lambda_chi, lambda_TV |

Outputs (`Res_map`, 4th dim is the channel):
1 `X_para` = χ+ (ppm, positive) · 2 `X_dia` = χ− stored as **positive magnitude** ·
3 phase_res · 4 a_map · 5 M0 · 6 R2star · 7 R2prime.

Demo defaults: `voxel_size=[1 1 2]`, `gamma=42.576`, `B0=3`, `a=323.5`, `tol_a=0.3`,
`lambda_r2prime=0.1`, `lambda_chi=10`, `lambda_TV=1`.

## 2. How QSM-CI maps its inputs (see `recon.m`)

- **magnitude** — `/input/magnitude.nii.gz` fed directly as `mag_img`.
- **local phase** — QSM-CI carries a single 3D `localfield.nii.gz` (ppm), not per-echo phase. `recon.m`
  re-projects it: `phi_e = localfield_ppm·1e-6·(gamma·1e6)·B0·2π·TE_e`.
- **R2 map** — not carried by the pipeline; `recon.m` estimates **R2\*** by a weighted log-linear fit
  over echoes and passes it as `r2_img`. R2\* = R2 + R2', so this over-estimates R2 (see Risks).
- **initial QSM** — `/input/chimap.nii.gz` (ppm) fed as `chi_img`.
- **params** — from `/input/params.json` (`B0`, `TE[s]`, `B0_dir`, `voxel_size`); remaining weights use
  the demo defaults.

## 3. Build the image

Once the solver exists, bake the code (no weights) into the image. Two paths:

**(a) MATLAB Runtime via `mcc`** (no run-time license needed at score time):

```bash
# on a machine with MATLAB + Compiler:
mcc -m recon.m \
    -a "$APART_HOME" \
    -a "$CHISEP_NIFTI" \
    -o apart_recon -d /opt/apart
# then build a Dockerfile FROM the matching MATLAB Runtime (R2023b / v912) that copies /opt/apart
docker build -t ghcr.io/astewartau/qsm-ci/apart-qsm:v1 algorithms/apart-qsm
```

**(b) Full MATLAB in-container** (needs a network license server at run time) — mirrors how the other
MATLAB χ-sep methods currently run via `--runner local` (`run.sh` with `matlab -batch`). Simplest for
Bunya where `module load matlab/R2023b` is available; no image build required for the PoC.

The `Dockerfile` (once added) is gitignored so CI pulls the prebuilt image, matching the other MATLAB
methods.

## 4. Push

```bash
docker push ghcr.io/astewartau/qsm-ci/apart-qsm:v1
```

## Risks / notes

- **Missing solver (blocker)** — `apart_qsm_single_ori.m` is not public. Everything else is scaffolded
  to its contract; nothing runs until it is obtained. This is the #1 risk.
- **R2 vs R2\*** — APART expects a true R2 map; we feed an R2\* proxy from the magnitude. R2\* includes
  the R2' contribution, so the a-map/decay fit will be biased. If a real R2 map (or a separate R2 vs R2'
  split) can be added to `/input`, prefer it. The pipeline already carries `r2prime.nii.gz`; a monoexp
  R2 fit would need the raw magnitude decay minus the R2' field term — not currently available.
- **Local phase reconstruction** — we synthesize per-echo local phase from a single ppm local field
  assuming perfect linearity in TE and no wrapping. Real per-echo local phase (if the pipeline exposes
  it) would be more faithful; `optional_inputs: [phase]` reserves raw phase for a future variant that
  does its own background removal.
- **B0/orientation** — demo hardcodes `B0=3`, `B0_dir=[0 0 1]`, `voxel_size=[1 1 2]`; `recon.m` reads
  these from `params.json` (our test set is `B0=7`, `voxel=[1 1 1]`, `B0_dir=[0 0 1]`). Confirm the
  solver honours non-default `params.B0`/`params.voxel_size`/`params.B0_dir` rather than assuming demo
  values internally.
- **`gamma` units** — demo `gamma=42.576` is MHz/T; `recon.m` multiplies by 1e6 to get Hz/T for the
  phase reconstruction. Keep this consistent with whatever the solver assumes internally.
- **NIfTI I/O** — the demo uses Jimmy Shen `save_nii`/`make_nii`; `recon.m` instead uses
  `load_untouch_nii`/`save_untouch_nii` from `$CHISEP_NIFTI` to preserve the input affine (matches the
  other χ-sep methods). Do not switch to `make_nii` (it discards the affine).
- **Runtime** — iterative fit over 4–6 echoes on a full 3D volume; expect minutes, not seconds. Set a
  generous Bunya/CI wall-clock.
