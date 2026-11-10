# toolbox-pipeline-qsmart

A whole-pipeline reference for QSMxT/QSM-CI#421: QSMART v1.0 with its own brainmask.m. See BUILD.md.

## Licence: FSL's bet2

The image contains FSL's `bet2` (Brain Extraction Tool, University of Oxford), built from Bostrix/FSL-BET2 d5acd7f for `brainmask.m`'s `bet2 -f 0.2`. FSL's licence
allows a transfer "done without financial return" provided its conditions are imposed on the
receiver and all original and amended source code is included. So the image carries, in
`/opt/FSL-BET2/`, the full bet2 source the binary was built from and the licence text (`LICENCE-FSL.txt`, the licence header of `bet2.cpp`), and its OCI
label `org.opencontainers.image.licenses` names it. Use of bet2 remains non-commercial, under
FSL's licence. Precedent: Neurodesk redistributes FSL publicly (Ashley, 2026-11-10).
