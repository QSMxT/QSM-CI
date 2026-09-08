# SUSEP-Net

A PyTorch network for susceptibility source separation: maps QSM, R2′ and the local field to
paramagnetic (χ+) and diamagnetic (χ−) source maps. Runs the authors' released weights on CPU.

- **Stage:** `chi-separation` (localfield, r2prime, chimap, mask → chi-para, chi-dia; ppm)
- **Engine:** PyTorch model (`susepnet_model.py`) + `recon.py`; see [BUILD.md](BUILD.md)
- **Code:** [github.com/YangGaoUQ/SUSEP-Net](https://github.com/YangGaoUQ/SUSEP-Net)
- **Licence:** see the repository; weights and normalisation statistics come from the authors'
  public release and are baked into the image.

## Preprocessing (from the authors' code)

- Input channels, in order: `[QSM, R2′, local field]`, each z-scored with the statistics in
  `all_mean_std.mat`.
- R2′ is fed raw, in Hz — no relaxivity (Dr) scaling, unlike χ-sepnet.
- Whole-volume inference (no patching).
- The final ReLU makes both outputs non-negative, so χ− arrives as the positive magnitude QSM-CI
  uses throughout.
