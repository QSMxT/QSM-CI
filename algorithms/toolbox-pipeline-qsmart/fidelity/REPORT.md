# toolbox-pipeline-qsmart: container fidelity

**PASS** (2026-11-10): the image `ghcr.io/astewartau/qsm-ci/qsmart-pipeline@sha256:6c6453186cc5b83864b5f765a4d388e235f8e77745099dfd5e85ae411a613092` computes
exactly what the same `recon.m` computes in licensed MATLAB R2023b (Update 5), at 8 threads.

| Case | Outputs compared | Result |
|---|---|---|
| `invivo` (s005001 Siemens Prisma bridge run, 184×256×128, 1 mm, 5 echoes) | `chimap`, and the intermediates `mask`, `R_0`, `tfs`, `totalfield`, `vesselness`, `vasc_only`, `bothat`, `lfs1`, `chi1`, `lfs2`, `chi2`, `chimap` | identical: 0 of 6,029,312 voxels differ in each, container vs licensed and licensed vs its repeat |

Run with `fidelity/matlab/submit.sh toolbox-pipeline-qsmart all` (v2: Slurm jobs 32553359–32553363). `FID_CASES="invivo=<cases>/invivo-pipeline"`.

## Notes
- **v2** runs N4 single-threaded (`ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=1`; algorithm.yml `ci_notes`), so
  the reference no longer depends on the host's core count. v1 (`sha256:c9ae67fa…`, N4 on every core)
  passed fidelity too, on a 32+-core node.
- **bet2 and N4.** `brainmask.m` shells out to `bet2` and to ANTs' `N4BiasFieldCorrection`. The
  licensed runs call the image's own binaries through wrappers in `$FID_ROOT/<slug>/bin`
  (`fid_setup_hook`), so both sides run the same `bet2` (Bostrix/FSL-BET2 d5acd7f, `../_bet2`) and
  the same N4. That makes this a check of the MATLAB, not of those two binaries.
- The image's Runtime (R2023b Update 11) and the licensed MATLAB (Update 5) are different updates
  of R2023b. The outputs are still identical.
- The patches QSM-CI applies to QSMART's code (the curvature guard, the Frangi `keyboard`) are
  listed with their diffs in `reports/deviations.diff` (BUILD.md).
