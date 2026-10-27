# amp-pe fidelity report

QSMxT/QSM-CI#300 (B2): does the `amp-pe` container compute what the authors' MATLAB computes? The
check is the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this
algorithm's [`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image
change.

- **Checked:** 2026-10-28, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the Wavelet Toolbox 23.2.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/amp-pe@sha256:0e1f44758045229f3297926a573e5664e6de5d2a895dca2a30d2f2339d507fc1`
  (`v2`), unchanged. Its `recon` was compiled with R2026a and runs on the R2026a MATLAB Runtime
  (image history; the Dockerfile recovered from it is committed).
- **Code:** `recon.m` as on `main` (the image's own), and EmoryCN2L/QSM_AMP_PE at `15bf8dc` assembled
  as BUILD.md does.
- **Cases:**
  - `sim`: QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 4 echoes, 1 mm,
    164×205×205), its ground-truth local field and the magnitude.
  - `invivo`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T,
    5 echoes, 1 mm, 184×256×128), with the local field and eroded mask derived once with QSMxT
    v10.0.0 (`fidelity/matlab/make_cases.sh`), and the magnitude.

## Result: identical

| Output | sim: container vs real | invivo: container vs real | real2 vs real (both) |
|---|---|---|---|
| `chimap.nii.gz` | identical | identical | identical |

No voxel differs, and every value is finite. The image predates `QSMCI_INTERMEDIATES`, so this
covers the final χ only. It was not rebuilt: it already reproduces licensed R2023b exactly, even
though it was compiled with R2026a. In the licensed runs the Wavelet Toolbox functions on the db1
path (`wavedec3`, `waverec3`, `wfilters`, `dbwavf`, `dwtmode`, `orthfilt`) resolve to R2023b's
`toolbox/wavelet/wavelet`. Some of AMP-PE's operator code calls `randn`; a fresh MATLAB and the
Runtime both start from the default seed, so any such draws match.

Container wall time was 10.2 min (sim) and 7.4 min (in vivo), with a peak RSS of 4.6 GB. Licensed
`recon.m` took 488–876 s.

## Slurm jobs

| What | Job ids |
|---|---|
| Setup and pull | 30730003 |
| sim: container, real, real2, compare | 30730004, 30730005, 30730006, 30730007 |
| invivo: container, real, real2, compare | 30730008, 30730009, 30730010, 30730011 |
