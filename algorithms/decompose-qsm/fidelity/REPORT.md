# decompose-qsm fidelity report

QSMxT/QSM-CI#300 (B2): does the `decompose-qsm` container compute what the original MATLAB computes?
The check is the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this
algorithm's [`config.sh`](config.sh); rerun it whenever `recon.m`, `decompose_utils/` or the image
change.

- **Checked:** 2026-10-31 (`v3`), on Slurm compute nodes, 8 CPUs per job (8 parpool workers).
  `v2` was checked on 2026-10-28.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the Optimization and Parallel
  Computing toolboxes 23.2.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/decompose-qsm@sha256:39a91b0435d6729cfd4a8c2441ebad1cbfe45c7358ea6d3ca95a1b65ec0e4033`
  (`v3`), pulled from GHCR by that digest. Its `recon` was compiled with licensed R2023b from this
  folder's `recon.m` and `decompose_utils/` (build job 31163541; `recon` sha256 `fdf43016…5331a2ec`, the same file in the
  image and in the build) and runs on the R2023b MATLAB Runtime.
- **Code:** `recon.m` and `decompose_utils/` as in this folder: `v2`'s, plus reading the optional
  per-echo χ(TE) `chimap-echoes.nii.gz` (#339). Licensed MATLAB runs the same files.
- **Previous image:** `v2` `sha256:a273a9b34f2863e4dac7e0c99f2c90e0dc220c56bf2e0f892c671a16be40112f`
  (identical to licensed MATLAB on 2026-10-28; it ignores `chimap-echoes`).
- **Fit region:** `DECOMPOSE_CROPBOX=32`, a 33³ central box (35 937 voxels), for every run alike.
  The fit is per voxel and independent between voxels, so the box checks it as well as the whole
  brain would; the whole brain takes hours on 8 cores.
- **Cases:**
  - `chisep-mc`: QSM-CI's default χ-separation phantom (7 T, 8 echoes, 1 mm, 164×205×205).
  - `invivo-nz`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T,
    5 echoes, 1 mm, 184×256×128), with χ and the eroded mask derived once with QSMxT v10.0.0
    (`fidelity/matlab/make_cases.sh`), and every zero of the magnitude raised to 1.
  - `chisep-mc-echoes`, `invivo-nz-echoes`: the same two cases plus a `chimap-echoes.nii.gz`, so the
    new code path runs. No dataset ships one yet, so it is synthetic: echo i is
    χ · (1 + 0.2 · (TE_i − TE_mid) / (TE_last − TE_first)), masked to the brain (float32), i.e.
    χ scaled from 0.9 at the first echo to 1.1 at the last. Any fixed input serves a fidelity check:
    the container and licensed MATLAB read the same file.

## Result: identical

| Output | chisep-mc | invivo-nz | chisep-mc-echoes | invivo-nz-echoes | real2 vs real (all four) |
|---|---|---|---|---|---|
| `chi-para.nii.gz` | identical | identical | identical | identical | identical |
| `chi-dia.nii.gz` | identical | identical | identical | identical | identical |

Each case column is the container vs licensed MATLAB (`real`). No voxel differs. `recon.m` writes no
intermediates, so this covers the outputs only.

- **The new path ran.** Every `-echoes` run, container and licensed, logs
  `DECOMPOSE: per-echo QSM (chimap-echoes.nii.gz)`; every run without the file logs the fallback,
  `no chimap-echoes.nii.gz; chi_total (chimap.nii.gz) for every echo`. With the per-echo input the
  fit differs from the fallback in 35 779–35 937 of the 35 937 fitted voxels (NRMSE 26 % / 30 % for
  χ+ / χ− on chisep-mc, 22 % / 6 % in vivo).
- **The fallback is unchanged.** On `chisep-mc` and `invivo-nz`, `v3`'s outputs are identical to
  `v2`'s licensed run of 2026-10-28.

**Why the in vivo case raises zero magnitudes.** On the unmodified in vivo case the reference fit
stops, in the container and in licensed MATLAB alike: `lsqcurvefit` reports "YDATA must be finite"
(`optimlib:lsqcurvefit:NonfiniteYdata`). The fit takes `log` of the complex signal, and this
acquisition's magnitude is exactly 0 in some echoes of some masked voxels (3.7 M zeros in the 4-D
volume), so `log(0)` is `-Inf`. That is the reference code's behaviour, not a container difference.
`invivo-nz` raises those zeros to 1 so the fit runs to the end.

## Slurm jobs

`v3` (2026-10-31; work root `matlab-fidelity/v3chk` on Bunya):

| What | Job ids |
|---|---|
| Compile (2026-10-30) | 31163541 |
| Pull (prep) and `-echoes` cases | 31191629, 31191947 |
| Setup | 31191957 |
| chisep-mc: container, real, real2, compare | 31191958, 31191959, 31191960, 31191961 |
| invivo-nz: container, real, real2, compare | 31191962, 31191963, 31191964, 31191965 |
| chisep-mc-echoes: container, real, real2, compare | 31191966, 31191967, 31191968, 31191969 |
| invivo-nz-echoes: container, real, real2, compare | 31191970, 31191971, 31191972, 31191973 |

`v2` (2026-10-28):

| What | Job ids |
|---|---|
| Setup and pull | 30730012 |
| chisep-mc: container, real, real2, compare | 30730013, 30730014, 30730015, 30730016 |
| invivo (unmodified; all three stop on log(0)): container, real, real2 | 30730017, 30730018, 30730019 |
| invivo-nz: container, real, real2, compare | 30731953, 30731954, 30731955, 30731956 |
