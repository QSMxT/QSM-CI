# qsmart-matlab fidelity check

Does the `qsmart-matlab` container compute what the authors' MATLAB computes? The container runs
on the MATLAB Runtime, which has no Image Processing or Statistics toolbox, so `../shims/` stands
in for 11 toolbox functions. This harness checks those shims, and the container as a whole,
against licensed MATLAB with the real toolboxes (QSMxT/QSM-CI#295, steps 1–2). The latest results
are in [`REPORT.md`](REPORT.md).

Rerun it whenever a shim, `recon.m`, `vasculature_mask_qsmci.m` or the image changes.

## What it runs

| Step | What | Where |
|---|---|---|
| `setup` | Pull the image by digest; assemble the build tree as in BUILD.md §1 (`assemble_deps.sh`); mex `eig3volume`; wrap the image's own `N4BiasFieldCorrection` so every run uses one N4 binary; diff QSM-CI's patched files against the authors' originals | Slurm |
| `shims` | `shim_fidelity.m`: each shim and its toolbox function on the same synthetic inputs, shaped like QSMART's calls | Slurm, licensed MATLAB |
| `container` | The pinned image under Apptainer, as `qsm_ci/containers.py` runs it | Slurm |
| `recon real`, `real2` | `recon.m` in licensed MATLAB with the real toolboxes, twice (the run-to-run floor) | Slurm, licensed MATLAB |
| `recon trace` | `recon.m` with the shims, where every shim call also runs the toolbox function and logs the difference (`fidelity_trace_setup.m`) | Slurm, licensed MATLAB |
| `recon real-single` | `real` with the vessel mask in single precision, as the authors' `vasculature_mask.m` runs it (informational) | Slurm, licensed MATLAB |
| `compare` | `compare_runs.m`: NRMSE, max difference and Dice per output | Slurm, licensed MATLAB |

The licensed runs write `recon.m`'s intermediates (`QSMCI_INTERMEDIATES`): vessel mask,
bottom-hat, vesselness, R_0, total field, and the local field and χ of each SDF stage. The shim run
against the real-toolbox run therefore shows which step a difference comes from. The container
image is compared on its final χ only, until it is rebuilt from a `recon.m` that has the option.

## Running it

On a host with Slurm, licensed MATLAB (`module load matlab/R2023b`, with the Image Processing and
Statistics toolboxes) and Apptainer on the compute nodes:

```bash
export FID_WORK=/path/to/work                      # needs a few GB; holds deps, the .sif, runs
export FID_QSMART=/path/to/QSMART                  # github.com/wtsyeda/QSMART
export FID_SUN=/path/to/sunhongfu-QSM              # github.com/sunhongfu/QSM (lapunwrap.m)
export FID_STI=/path/to/STISuite_V3.0/STISuite_V3.0
export FID_CASES="sim=/path/sim/inputs invivo=/path/acquisition/inputs"   # contract inputs
export SBATCH_ACCOUNT=... SBATCH_PARTITION=...   # and SBATCH_QOS if the default QOS queues
bash algorithms/qsmart-matlab/fidelity/submit.sh all     # or: setup | shims | runs | compare
```

`submit.sh` only calls `sbatch`; all MATLAB, mex and Apptainer work happens in `job.sh` on compute
nodes. The image defaults to `image:` in `../algorithm.yml` (override with `FID_IMAGE`). Results:
`$FID_WORK/reports/` (`shims/shim_fidelity.md/.json`, `runs-<case>.md/.json`, `deviations.diff`) and
`$FID_WORK/runs/<case>/trace/trace/trace.tsv` (every shim call in the pipeline). Copy the tables
into `REPORT.md`.

## Pass rules

- **Shims:** identical results for `strel`, `padarray`, the morphology functions and
  `graythresh`; max relative error ≤ 1e-10 for `imfilter` and `imgaussfilt3` (1e-5 on single-precision input), ≤ 1e-12 for
  `prctile`. Forms a shim doesn't claim to support are reported, not scored.
- **Container:** the shim run matches the real-toolbox run within the real-toolbox run-to-run
  floor, and the container's χ matches the licensed runs. When everything passes, record the
  checked digest in `../algorithm.yml` under `fidelity:`.
