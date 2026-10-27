# qsmart-matlab fidelity check

Does the `qsmart-matlab` container compute what the authors' MATLAB computes? `recon` is compiled
with licensed MATLAB R2023b against the real Image Processing Toolbox and runs on the R2023b
MATLAB Runtime. This harness runs the pinned image and the same `recon.m` in licensed R2023b, and
compares every intermediate and the final χ (QSMxT/QSM-CI#295, steps 1–2). The latest results
are in [`REPORT.md`](REPORT.md).

Rerun it whenever `recon.m`, `vasculature_mask_qsmci.m` or the image changes.

## What it runs

| Step | What | Where |
|---|---|---|
| `setup` | Pull the image by digest; assemble the build tree as in BUILD.md §1 (`assemble_deps.sh`); mex `eig3volume`; wrap the image's own `N4BiasFieldCorrection` so every run uses one N4 binary; diff QSM-CI's patched files against the authors' originals | Slurm |
| `container` | The pinned image under Apptainer, as `qsm_ci/containers.py` runs it, with `QSMCI_INTERMEDIATES` set | Slurm |
| `recon real`, `real2` | `recon.m` in licensed MATLAB with the real toolboxes, twice (the run-to-run floor) | Slurm, licensed MATLAB |
| `compare` | `compare_runs.m`: NRMSE, max difference and Dice per output, and where each toolbox function resolved in each run | Slurm, licensed MATLAB |

Every run writes `recon.m`'s intermediates (`QSMCI_INTERMEDIATES`): vessel mask, bottom-hat,
vesselness, R_0, total field, the local field and χ of each SDF stage, and the final χ, plus
`intermediates.json` (Otsu threshold, N4 status, thread count, and the path each toolbox function
resolved to). Comparing them shows which step a difference comes from. All jobs use the same CPU
count (8), because the thread count changes iLSQR's rounding.

## Running it

On a host with Slurm, licensed MATLAB (`module load matlab/R2023b`, with the Image Processing
Toolbox) and Apptainer on the compute nodes:

```bash
export FID_WORK=/path/to/work                      # needs a few GB; holds deps, the .sif, runs
export FID_QSMART=/path/to/QSMART                  # github.com/wtsyeda/QSMART
export FID_SUN=/path/to/sunhongfu-QSM              # github.com/sunhongfu/QSM (lapunwrap.m)
export FID_STI=/path/to/STISuite_V3.0/STISuite_V3.0
export FID_CASES="sim=/path/sim/inputs invivo=/path/acquisition/inputs"   # contract inputs
export SBATCH_ACCOUNT=... SBATCH_PARTITION=...   # and SBATCH_QOS if the default QOS queues
bash algorithms/qsmart-matlab/fidelity/submit.sh all     # or: setup | runs | compare
```

`submit.sh` only calls `sbatch`; all MATLAB, mex and Apptainer work happens in `job.sh` on compute
nodes. The image defaults to `image:` in `../algorithm.yml` (override with `FID_IMAGE`). Results:
`$FID_WORK/reports/` (`runs-<case>.md/.json`, `deviations.diff`, `env.json`). Copy the tables
into `REPORT.md`.

## Pass rule

Every output (each intermediate and the final χ) of the container is identical to licensed
MATLAB with the real toolboxes, at the same thread count, in every case. When it passes, record
the checked digest in `../algorithm.yml` under `fidelity:`.
