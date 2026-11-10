# toolbox-pipeline-qsmart: container fidelity

**PASS** (2026-11-10): the image `ghcr.io/astewartau/qsm-ci/qsmart-pipeline@sha256:c9ae67faab17cc979e8116554121fe12bb2ec3bde1f5c41fee038958599e62c2` computes
exactly what the same `recon.m` computes in licensed MATLAB R2023b (Update 5), at 8 threads.

| Case | Outputs compared | Result |
|---|---|---|
| `invivo` (s005001 Siemens Prisma bridge run, 184×256×128, 1 mm, 5 echoes) | `chimap`, and the intermediates `mask`, `R_0`, `tfs`, `totalfield`, `vesselness`, `vasc_only`, `bothat`, `lfs1`, `chi1`, `lfs2`, `chi2`, `chimap` | identical: 0 of 6,029,312 voxels differ in each, container vs licensed and licensed vs its repeat |

Run with `fidelity/matlab/submit.sh toolbox-pipeline-qsmart all`: container job 32542839, then
licensed runs 32544135–32544136 and compare 32544137 (`FID_RUNS="real real2"`, once the licensed
runs had bet2). `FID_CASES="invivo=<cases>/invivo-pipeline"`.

## Notes
- **bet2 and N4.** `brainmask.m` shells out to `bet2` and to ANTs' `N4BiasFieldCorrection`. The
  licensed runs call the image's own binaries through wrappers in `$FID_ROOT/<slug>/bin`
  (`fid_setup_hook`), so both sides run the same `bet2` (Bostrix/FSL-BET2 d5acd7f, `../_bet2`) and
  the same N4. That makes this a check of the MATLAB, not of those two binaries.
- The image's Runtime (R2023b Update 11) and the licensed MATLAB (Update 5) are different updates
  of R2023b. The outputs are still identical.
- The patches QSM-CI applies to QSMART's code (the curvature guard, the Frangi `keyboard`) are
  listed with their diffs in `reports/deviations.diff` (BUILD.md).
