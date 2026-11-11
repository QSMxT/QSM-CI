# toolbox-pipeline-decompose-qsmci: container fidelity

**PASS** (2026-11-10): the image `ghcr.io/astewartau/qsm-ci/decompose-pipeline@sha256:f9ada5009494cdb7c02c12fc7c90f9d91418627bc266e22e3b308f4c5464456c`
(v3) computes exactly what the same `recon.m` computes in licensed MATLAB R2023b (Update 5),
at 8 threads.

| Case | Outputs compared | Result |
|---|---|---|
| `invivo` (s005001 Siemens Prisma bridge run, 184×256×128, 1 mm, 5 echoes, with its R2′ map), `DECOMPOSE_CROPBOX=32` | `chi-para`, `chi-dia`, `chimap`, and the intermediates `mask`, `mask_vsharp`, `chimap_echo1`–`5`, `c_plus`, `c_minus`, `c_zero`, `r2star0`, `chi_plus`, `chi_minus` | identical: 0 of 6,029,312 voxels differ in each, container vs licensed and licensed vs its repeat |

Run with `fidelity/matlab/submit.sh toolbox-pipeline-decompose-qsmci all` (Slurm: setup 32547244, runs 32547245–32547247, compare 32547248).

## Notes
- **The fit covers a 33³ central box** (`DECOMPOSE_CROPBOX=32`), as decompose-qsm's fidelity check does. The fit is per voxel and independent between voxels, and the whole brain takes hours. Everything before the fit (BET, unwrapping, V-SHARP, STAR-QSM per echo) runs on the whole volume.
- **Earlier images.** v1 and v2 lacked STI Suite's `Support_Functions` (`qsm_kiwi_1`'s `@iFDF` and SpaRSA's `soft`), which `QSM_star` calls. A voxel with a zero-magnitude echo is now left at 0 (there is no log to fit), and BET runs with FSL's left-right flip, as the paper's "BET in FSL" does.
- **bet2 mex.** This is MEDI's bet2 mex, as in toolbox-pipeline-medi-cornell. The licensed runs preload the host's libstdc++ (`FID_MATLAB_ENV`).
- The image's Runtime (R2023b Update 11) and the licensed MATLAB (Update 5) are different updates
  of R2023b. The outputs are still identical.
