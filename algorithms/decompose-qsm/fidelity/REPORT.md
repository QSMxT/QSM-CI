# decompose-qsm fidelity report

QSMxT/QSM-CI#300 (B2): does the `decompose-qsm` container compute what the original MATLAB computes?
The check is the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this
algorithm's [`config.sh`](config.sh); rerun it whenever `recon.m`, `decompose_utils/` or the image
change.

- **Checked:** 2026-10-28, on Slurm compute nodes, 8 CPUs per job (8 parpool workers).
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the Optimization and Parallel
  Computing toolboxes 23.2.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/decompose-qsm@sha256:a273a9b34f2863e4dac7e0c99f2c90e0dc220c56bf2e0f892c671a16be40112f`
  (`v2`), unchanged. Its `recon` was compiled with R2023b and runs on the R2023b MATLAB Runtime
  (image history; the Dockerfile recovered from it is committed).
- **Code:** `recon.m` and `decompose_utils/` as on `main` (the image's own).
- **Fit region:** `DECOMPOSE_CROPBOX=32`, a 33³ central box (35 937 voxels), for every run alike.
  The fit is per voxel and independent between voxels, so the box checks it as well as the whole
  brain would; the whole brain takes hours on 8 cores.
- **Cases:**
  - `chisep-mc`: QSM-CI's default χ-separation phantom (7 T, 8 echoes, 1 mm, 164×205×205).
  - `invivo-nz`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T,
    5 echoes, 1 mm, 184×256×128), with χ and the eroded mask derived once with QSMxT v10.0.0
    (`fidelity/matlab/make_cases.sh`), and every zero of the magnitude raised to 1.

## Result: identical

| Output | chisep-mc: container vs real | invivo-nz: container vs real | real2 vs real (both) |
|---|---|---|---|
| `chi-para.nii.gz` | identical | identical | identical |
| `chi-dia.nii.gz` | identical | identical | identical |

No voxel differs. The image predates `QSMCI_INTERMEDIATES`, so this covers the outputs only. It was
not rebuilt: it already reproduces licensed R2023b exactly.

**Why the in vivo case raises zero magnitudes.** On the unmodified in vivo case the reference fit
stops, in the container and in licensed MATLAB alike: `lsqcurvefit` reports "YDATA must be finite"
(`optimlib:lsqcurvefit:NonfiniteYdata`). The fit takes `log` of the complex signal, and this
acquisition's magnitude is exactly 0 in some echoes of some masked voxels (3.7 M zeros in the 4-D
volume), so `log(0)` is `-Inf`. That is the reference code's behaviour, not a container difference.
`invivo-nz` raises those zeros to 1 so the fit runs to the end.

## Slurm jobs

| What | Job ids |
|---|---|
| Setup and pull | 30730012 |
| chisep-mc: container, real, real2, compare | 30730013, 30730014, 30730015, 30730016 |
| invivo (unmodified; all three stop on log(0)): container, real, real2 | 30730017, 30730018, 30730019 |
| invivo-nz: container, real, real2, compare | 30731953, 30731954, 30731955, 30731956 |
