# toolbox-pipeline-medi-cornell: container fidelity

**PASS** (2026-11-10): the image `ghcr.io/astewartau/qsm-ci/medi-pipeline@sha256:de46335d78a05726405fe596c1f3e22347b654e9b5929cd3b5668c1c36c246c6` computes
exactly what the same `recon.m` computes in licensed MATLAB R2023b (Update 5) with the MEDI toolbox
2024.11.26, at 8 threads.

| Case | Outputs compared | Result |
|---|---|---|
| `invivo` (s005001 Siemens Prisma bridge run, 184×256×128, 1 mm, 5 echoes, ImagingFrequency 123.249 MHz) | `chimap`, and the intermediates `ifreq_raw`, `totalfield`, `n_std`, `mask`, `mask_csf`, `r2star`, `localfield` | identical: 0 of 6,029,312 voxels differ in each, container vs licensed and licensed vs its repeat |

Run with `fidelity/matlab/submit.sh toolbox-pipeline-medi-cornell all` (Slurm jobs 32543375–32543379
and compare 32544133), `FID_CASES="invivo=<cases>/invivo-pipeline"`.

## Notes
- **bet2 mex.** MEDI's `BET.m` calls the bet2 mex built from the toolbox's FSL sources. They need
  C++98 (`fidelity/matlab/mex_bet2.m`). The image builds the mex with its own compiler. On Bunya,
  the host's g++ 11 links it against `GLIBCXX_3.4.29`, newer than the libstdc++ R2023b loads first.
  The licensed runs therefore preload the host's libstdc++ (`FID_MATLAB_ENV`, MathWorks'
  workaround). It changes which library loads, not what the code computes.
- The image's Runtime (R2023b Update 11) and the licensed MATLAB (Update 5) are different updates
  of R2023b. The outputs are still identical.
- Where every toolbox function resolved, in each run: `intermediates.json` in the runs
  (`resolved`). Every function resolved to the MEDI toolbox copy under `deps/medi` (licensed) or the
  same files in the image's CTF (container).
