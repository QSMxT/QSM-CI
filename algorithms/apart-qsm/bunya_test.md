# Validating APART-QSM on Bunya (no local MATLAB license)

We cannot run MATLAB locally, so validate the scaffold on Bunya HPC (has `module load matlab/R2023b`).

## Prerequisites (one-time, on Bunya)

1. **Get the core solver.** The public repo does NOT ship `apart_qsm_single_ori.m` (see BUILD.md §0).
   Obtain it from the authors and drop it (plus any private deps and `save_nii`/`make_nii` if used)
   into the `single_orientation/` folder that `$APART_HOME` points at.

2. **Clone the repo + NIfTI toolbox on Bunya:**
   ```bash
   git clone https://github.com/AMRI-Lab/APART-QSM ~/repos/APART-QSM
   # NIfTI I/O (Jimmy Shen). Reuse the one already vendored in qsm-ci:
   #   algorithms/matlab-tkd/nifti  (load_untouch_nii / save_untouch_nii)
   ```

## 1. rsync from this machine to Bunya

```bash
# the algorithm folder (recon.m + run.sh)
rsync -av /home/ashley/repos/qsm/qsmci/qsmci/algorithms/apart-qsm/ \
          bunya:~/repos/qsm-ci/algorithms/apart-qsm/

# the test dataset (inputs + ground truth)
rsync -av /home/ashley/repos/qsm/qsmci/qsmci/data/sim/chisep/ \
          bunya:~/qsm-ci-test/chisep/

# the NIfTI I/O toolbox (if not already on Bunya)
rsync -av /home/ashley/repos/qsm/qsmci/qsmci/algorithms/matlab-tkd/nifti/ \
          bunya:~/repos/qsm-ci/algorithms/matlab-tkd/nifti/
```

## 2. Set env + run (interactive session or SLURM job)

```bash
module load matlab/R2023b

export APART_HOME=$HOME/repos/APART-QSM/single_orientation
export CHISEP_NIFTI=$HOME/repos/qsm-ci/algorithms/matlab-tkd/nifti

IN=$HOME/qsm-ci-test/chisep/inputs
OUT=$HOME/qsm-ci-test/chisep/out-apart
mkdir -p "$OUT"

# Option A — via run.sh (mirrors how QSM-CI invokes it)
cd $HOME/repos/qsm-ci/algorithms/apart-qsm
APART_HOME=$APART_HOME CHISEP_NIFTI=$CHISEP_NIFTI bash run.sh "$IN" "$OUT"

# Option B — standalone matlab -batch (equivalent to what run.sh does)
matlab -batch "addpath('$HOME/repos/qsm-ci/algorithms/apart-qsm'); recon('$IN','$OUT')"
```

Expected outputs: `$OUT/chi-para.nii.gz` (χ+) and `$OUT/chi-dia.nii.gz` (χ−, positive magnitude), both
3D, single-precision, on the input grid/affine (164×205×205, voxel 1×1×1 mm).

## 3. Sanity checks

- Both files exist, are 3D, single, and share the input affine (`fslhd` / `nib`).
- χ+ and χ− are both non-negative inside the mask; magnitudes physical (roughly a few tenths of a ppm
  in tissue; deep grey nuclei higher).
- Compare against ground truth `~/qsm-ci-test/chisep/groundtruth/chi-para.nii.gz` and `chi-dia.nii.gz`
  (e.g. NRMSE / correlation with `fslmaths`/python). This is the same metric QSM-CI scores with.

## 4. If it errors

- `Undefined function 'apart_qsm_single_ori'` → the core solver is missing (Prerequisite 1).
- `Undefined function 'load_untouch_nii'` → `$CHISEP_NIFTI` wrong / toolbox not synced.
- Solver ignores `params.B0`/`params.voxel_size`/`params.B0_dir` and assumes demo values (3 T, [1 1 2]
  mm) → it was written only for the demo geometry; patch it to honour `params` (BUILD.md Risks).
- Poor separation → likely the R2\*-as-R2 approximation or the synthesized per-echo local phase
  (BUILD.md Risks); try feeding a true R2 map if one can be produced on Bunya.

## Notes on the geometry mismatch vs the demo

The demo data is 240×240×80 @ [1 1 2] mm, B0=3 T; our test set is 164×205×205 @ [1 1 1] mm, B0=7 T.
`recon.m` drives everything from `params.json`, so the wrapper adapts — but confirm the **solver**
itself is geometry-agnostic and does not hardcode the demo values internally.
