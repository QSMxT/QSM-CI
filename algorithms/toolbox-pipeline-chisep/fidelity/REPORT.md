# toolbox-pipeline-chisep: container fidelity

**PASS** (2026-11-10): the image `ghcr.io/astewartau/qsm-ci/chisep-pipeline@sha256:17e9784a259dfc917aa238d7418ce8bd1af07c3c2e35fbe57e281b2b8b3c1f96`
(v3) computes exactly what the same `recon.m` computes in licensed MATLAB R2023b (Update 5),
at 8 threads.

| Case | Outputs compared | Result |
|---|---|---|
| `invivo` (s005001 Siemens Prisma bridge run, 184×256×128, 1 mm, 5 echoes, with its R2′ map), method `ilsqr` | `chi-para`, `chi-dia`, `chimap`, and the intermediates `mask`, `totalfield`, `n_std`, `r2star`, `localfield`, `mask_vsharp` | identical: 0 of 6,029,312 voxels differ in each, container vs licensed and licensed vs its repeat |
| `invivo-medi` (the same, `config.json` method `medi`) | the same | identical |

Run with `fidelity/matlab/submit.sh toolbox-pipeline-chisep all` (Slurm: setup 32547235, `invivo` 32547236–32547239, `invivo-medi` 32547240–32547243).

## Notes
- **Earlier images.** v1 lacked `tukeywin`, and v2 lacked `lsqnonlin`. The χ-separation toolbox's pcode calls both: `tukey_windowing` calls `tukeywin`, and `r2star_nnls` calls `lsqnonlin` inside a parfor. mcc can't trace into pcode, so `recon.m`'s pragma names them. The `trace` profile does not follow code into parfor workers, so it missed `lsqnonlin`. A container run found it.
- **bet2 mex.** This is MEDI's `BET.m` with its bet2 mex, as in toolbox-pipeline-medi-cornell. The licensed runs preload the host's libstdc++ (`FID_MATLAB_ENV`).
- **ROMEO.** The image and the licensed runs use the same mritools 4.7.1 `romeo` binary (`MRITOOLS_ROMEO`).
- The image's Runtime (R2023b Update 11) and the licensed MATLAB (Update 5) are different updates
  of R2023b. The outputs are still identical.
