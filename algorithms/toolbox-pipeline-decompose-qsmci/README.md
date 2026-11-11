# toolbox-pipeline-decompose-qsmci

A whole-pipeline reference for QSMxT/QSM-CI#421; see BUILD.md for what it runs and how it is built.

## Licence: FSL's bet2

The image contains FSL's `bet2` (Brain Extraction Tool, University of Oxford), compiled as the mex MEDI's `BET.m` calls, from the bet2 sources the MEDI toolbox ships in `functions/bet2/`. FSL's licence
allows a transfer "done without financial return" provided its conditions are imposed on the
receiver and all original and amended source code is included. So the image carries, in
`/opt/fsl-bet2/`, the full bet2 source the binary was built from and the licence text (`licence.html`, shipped with those sources), and its OCI
label `org.opencontainers.image.licenses` names it. Use of bet2 remains non-commercial, under
FSL's licence. Precedent: Neurodesk redistributes FSL publicly (Ashley, 2026-11-10).
