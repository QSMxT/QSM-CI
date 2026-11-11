# STI Suite pipeline (STI Suite 3.0 QSM_GUI, iLSQR)

The reference for QSMxT's `sti-suite-ilsqr` pipeline (QSMxT/QSM-CI#421): STI Suite 3.0's QSM_GUI
iLSQR path, run as the GUI runs it. `recon.m` lists the chain step by step.

## How the chain was found
QSM_GUI and its glue are P-code with figures. The GUI was driven headless in licensed MATLAB
R2023b (Update 5) on the QSM-CI in-vivo s005001 Prisma scan, with every function it calls logged
(arguments, outputs, call stack). Its buttons were pressed as a user would: "Thresholding" (the
level `thresh_tool` starts at; the GUI keeps it unless the user drags the line), then "V-SHARP",
then "iLSQR". The glue the GUI runs between STI Suite's functions (the threshold, the largest
component, the filled bounding box) is written out in `recon.m`. Every computation is STI Suite's
own function or the MATLAB function the GUI calls.

## Fidelity against the GUI
`recon.m`, run in licensed MATLAB on the same data as the GUI probe (2026-11-11), against the GUI's
own stored χ:
- threshold level 40.156864: identical
- thresholding mask (1,572,934 voxels): identical
- PolishMask's mask (1,265,491 voxels): identical
- χ: max |Δ| 4.4e-7 ppm, NRMSE 1.2e-4 %

The GUI hands V_SHARP its mask with only the slices up to its bounding box's last (126 of 128
here). `recon.m` keeps the volume's size, and the difference above (thread count and that) is
immaterial.

The GUI's B0 and H fields are what the user types; `recon.m` takes params.json's `B0` and `B0_dir`.
STI Suite's "single button" (STAR-QSM) masks with the P-coded `Getmasking` instead, which is not
part of this reference.

## Licence
STI Suite is the Chunlei Liu lab's software (https://people.eecs.berkeley.edu/~chunlei.liu/software.html);
see the STI Suite licence, as for `ilsqr-sti`.
