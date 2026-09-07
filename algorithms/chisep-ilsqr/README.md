# χ-separation (iLSQR)

The iLSQR variant of the SNU-LIST χ-separation toolbox: splits net susceptibility into a
paramagnetic (χ+, iron) and a diamagnetic (χ−, myelin/calcium) source using the local field and an
R2′ map to break the para/dia degeneracy. A classical iterative baseline.

- **Stage:** `chi-separation` (localfield, r2prime, magnitude, mask → chi-para, chi-dia; ppm)
- **Engine:** compiled MATLAB (MATLAB Runtime image; see [BUILD.md](BUILD.md))
- **Reference:** Shin et al., NeuroImage 2021 · doi:[10.1016/j.neuroimage.2021.118371](https://doi.org/10.1016/j.neuroimage.2021.118371)
- **Licence:** academic use; toolbox obtained via the SNU-LIST Google Form, so it is baked into the
  image and not redistributed here.

## How QSM-CI runs it

`run.sh` calls the compiled `recon`, which (1) reconstructs a QSM from the input local field with
STI-Suite's own `QSM_iLSQR` and (2) feeds that QSM, the local field and R2′ to `chi_sep_iLSQR`.

## Why the QSM is reconstructed in-house

The toolbox's streaking and NNLS steps are tuned to the scaling and orientation conventions of a QSM
it produced itself. Feeding it an external χ map — the phantom's ground-truth χ_total, in the first
attempt — gave a ~10× underestimated output with the calcification missing, R2′ having no effect and
NNLS never converging. Reconstructing the QSM with STI-Suite's `QSM_iLSQR` from the same local field
fixed all of that (χ+ correlation 0.27 → 0.84, cross-contamination leakage ~70× lower). A CSF mask
and a measured noise-level map (`N_std`) changed nothing. So the phantom supplies a field, and this
submission builds the toolbox-native QSM it needs before separating.
