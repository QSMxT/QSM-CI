# WaveSep

A wavelet-based iterative approach to susceptibility source separation: splits χ_total into
paramagnetic (χ+) and diamagnetic (χ−) sources under two voxel-wise data-fidelity terms
(χ+ + χ− ≈ χ_total, χ+ − χ− ≈ R2′/Dr) and a wavelet-domain L1 sparsity prior, solved by proximal
gradient (ISTA-style soft-thresholding, `db4`). Pure NumPy + PyWavelets on CPU — no network, no
pretrained weights, no GPU. Converges in roughly a dozen iterations (early stop).

- **Stage:** `chi-separation` (chimap, r2prime, mask → chi-para, chi-dia; ppm)
- **Engine:** the authors' solver (`wavesep/qsm_sep.py`) driven by our thin `recon.py`; see [BUILD.md](BUILD.md)
- **Reference:** Fang, Shin, van Zijl, Li, Sulam, "WaveSep: A Flexible Wavelet-Based Approach for
  Source Separation in Susceptibility Imaging", MLCN (MICCAI workshop) 2023 ·
  doi:[10.1007/978-3-031-44858-4_6](https://doi.org/10.1007/978-3-031-44858-4_6)
- **Code:** [github.com/ZhenghanFang/WaveSep](https://github.com/ZhenghanFang/WaveSep)
- **Licence:** the repository declares none; the author granted academic-use permission for this
  benchmark, so the source is baked into the image and not redistributed here.

## Notes

- The paper's "learned proximal operator" refers to the upstream dipole inversion; WaveSep itself
  takes a pre-reconstructed QSM as input, so this submission consumes `chimap` rather than the field.
- The solver supports several head orientations (lists of R2′ + B0 directions) and, since 2025-04,
  `Dr_pos ≠ Dr_neg`. QSM-CI's phantoms are single-orientation, so that multi-orientation advantage
  does not show here; it still leads the iterative χ-separation methods on χ+.
- The solver expects LPS-oriented volumes for multi-orientation input; single-orientation data, as
  here, needs no reorientation (see the note at the top of `recon.py`).
