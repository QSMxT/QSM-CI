# toolbox-pipeline-sti: container fidelity

**PASS** (2026-11-11): the image `ghcr.io/astewartau/qsm-ci/sti-pipeline@sha256:60dcc483e1a6a4c18c04d8e2bda99923cdb72673f774622f67c952dfd52a7dd8` computes
exactly what the same `recon.m` computes in licensed MATLAB R2023b (Update 5) with STI Suite 3.0,
at 8 threads.

| Case | Outputs compared | Result |
|---|---|---|
| `invivo` (s005001 Siemens Prisma bridge run, 184×256×128, 1 mm, 5 echoes, TE 5:6:29 ms, ImagingFrequency 123.249 MHz) | `chimap`, and the intermediates `mask`, `mask_bfr`, `totalfield`, `localfield` | identical: 0 of 6,029,312 voxels differ in each, container vs licensed. Threshold level 40.156864 and middle slice 64 in both `intermediates.json` |

The licensed side is the run that checked `recon.m` against the GUI itself (README.md, Fidelity
against the GUI: χ within 4.4e-7 ppm of the GUI's own, level and masks identical). The container side
is the image run with podman on the same input (`QSMCI_INTERMEDIATES=1`, `--cpus 4`; MATLAB still
reports 8 computational threads).

## Notes
- The image's Runtime (R2023b Update 11) and the licensed MATLAB (Update 5) are different updates
  of R2023b. The outputs are still identical.
- STI Suite is pcode, bundled whole with `mcc -a sti` (BUILD.md). Where every function resolved:
  `intermediates.json` (`resolved`). In the container, `MRPhaseUnwrap`, `V_SHARP`, `PolishMask` and
  `QSM_iLSQR` resolved to the bundled STI Suite `.p` files, and the Image Processing Toolbox
  functions to the Runtime's copies.
