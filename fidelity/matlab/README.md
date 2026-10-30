# MATLAB container fidelity

Does a compiled MATLAB container compute what the authors' MATLAB computes? This harness compiles an
algorithm's `recon.m` against the real toolboxes, runs the pinned image and the same `recon.m` in
licensed MATLAB on the same inputs, and compares every output and intermediate
(QSMxT/QSM-CI#295, #300). Each algorithm supplies only its inputs and its entry point, in
`algorithms/<slug>/fidelity/config.sh`; its results go in `algorithms/<slug>/fidelity/REPORT.md`
and the `fidelity:` block of its `algorithm.yml`.

Rerun an algorithm's check whenever its `recon.m`, its dependencies or its image change.

## What it runs

`submit.sh <slug> <step>` submits Slurm jobs; the login node only runs `sbatch`.

| Step | What |
|---|---|
| `build` | Compile `recon.m` with licensed R2023b and the MATLAB Compiler, against the real toolboxes, with no shims. Records what each function in `FID_WHICH` resolves to, the products the code needs, `requiredMCRProducts.txt`, and fails if `unresolvedSymbols.txt` or `mccExcludedFiles.log` lists anything. Leaves `recon` in `$FID_ROOT/<slug>/build/out/` and the log in `reports/build.txt`. |
| `trace` | Profile one licensed run and list every function outside core MATLAB that the code reaches, pcode included (`reports/trace.txt`). mcc can't trace into pcode, so the toolbox functions only pcode calls must be named in `recon.m`'s `%#function` pragma; this is how to find them. |
| `setup` | Pull the image by digest to a `.sif`; assemble the dependencies as the build does. |
| `container` | The image under Apptainer, as `qsm_ci/containers.py` runs it, with `QSMCI_INTERMEDIATES` set. |
| `recon` (`real`, `real2`) | The same `recon.m` in licensed MATLAB with the real toolboxes, twice: the second run is the run-to-run floor. |
| `compare` | `compare_runs.m` on every NIfTI `real` writes, top level and `intermediates/`: NRMSE, max difference, differing voxels, Dice for binary outputs, and each run's `intermediates.json`. |

`all` is `setup`, the three runs and `compare`, per case. Every run job gets 8 CPUs, because the
thread count changes the rounding of multithreaded solvers.

## The pass bar

Every output and intermediate of the container is identical to licensed MATLAB, at the same thread
count, in every case. `compare` writes `PASS` or `FAIL` at the top of `reports/runs-<case>.md`. A
residual is never accepted as a tolerance: find its cause and record it in the algorithm's REPORT.md.

## Per-algorithm config

`algorithms/<slug>/fidelity/config.sh` is sourced by bash and sets:

| Variable | Meaning |
|---|---|
| `FID_SIF` | the `.sif` name prefix (one `.sif` per image digest) |
| `FID_SOURCES` | the environment variables naming the source folders `fid_assemble` reads |
| `fid_assemble DEST ALGO` | lays the dependencies out in `DEST`, exactly as BUILD.md does for the compile |
| `FID_MATLAB_PATH` | folders under `DEST` on the MATLAB path, highest priority first; `+dir` adds subfolders |
| `FID_MCC_A` | folders under `DEST` mcc must force-bundle (`-a`; pcode, mex, classes), or `@path` under `matlabroot` |
| `FID_WHICH` | functions whose resolution the build and the licensed runs record |
| `FID_ENV` | optional `K=V` pairs set for every run, licensed and container alike |
| `FID_SBATCH` | optional extra `sbatch` arguments for the run jobs (memory, time) |
| `fid_build_hook`, `fid_setup_hook` | optional steps after `fid_assemble` (e.g. a mex compile) |

`recon.m` writes its intermediates when `QSMCI_INTERMEDIATES` is set (a directory, or `1` for
`<out>/intermediates`): float64 NIfTIs of its meaningful steps, plus `intermediates.json` with the
MATLAB version, the thread count and where each toolbox function in its pragma resolved. Unset,
nothing changes.

## Running it

On a host with Slurm, licensed MATLAB R2023b (`module load matlab/R2023b`, with the toolboxes the
algorithm needs) and Apptainer on the compute nodes:

```bash
export FID_ROOT=/path/to/work               # tens of GB: one .sif per image, the runs
export SBATCH_ACCOUNT=... SBATCH_PARTITION=...
export FID_STI=... FID_NIFTI=...            # the sources the algorithm's FID_SOURCES lists
export FID_CASES="sim=/path/sim/inputs invivo=/path/invivo/inputs"   # its stage's contract inputs
bash fidelity/matlab/submit.sh ilsqr-sti build     # compile; then build and push the image
bash fidelity/matlab/submit.sh ilsqr-sti all       # the check, against image: in algorithm.yml
```

`FID_IMAGE` overrides `image:`. `FID_RUNS` picks some of `container real real2`. `FID_TAG` with
`FID_ALGO_SRC` or different sources checks another copy as a licensed run named `real-<tag>` (for
example another toolbox release), which `compare` adds to the table.

Results: `$FID_ROOT/<slug>/reports/` (`build.txt`, `trace.txt`, `env.json`, `runs-<case>.md` and
`.json`). Copy the tables into the algorithm's REPORT.md.

## Cases

`make_cases.sh` (a Slurm job) lays out the cases each stage needs from three contract datasets:

| Case | Stage | From |
|---|---|---|
| `sim` (end-to-end) | `end-to-end` | QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 4 echoes, 1 mm, 164×205×205) |
| `invivo` (end-to-end) | `end-to-end` | one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T, 5 echoes, 184×256×128) |
| `sim-bfr`, `sim-dipole` | `bfr`, `dipole` | the in-silico head's ground-truth total and local field |
| `invivo-bfr`, `invivo-dipole`, `invivo-chisep` | `bfr`, `dipole`, `chi-separation` | derived once from the in vivo acquisition with QSMxT v10.0.0: ROMEO total field, V-SHARP local field and its eroded mask, RTS χ, R2′ = 0.52·R2* |
| `chisep-mc` | `chi-separation` | QSM-CI's default χ-separation phantom (7 T, 8 echoes) |
| `invivo-chisep-nz` | `chi-separation` | `invivo-chisep` with the magnitude's zeros raised to 1, for DECOMPOSE (its fit takes `log` of the signal) |

Any fixed input serves a fidelity check, since the container and licensed MATLAB read the same files.
