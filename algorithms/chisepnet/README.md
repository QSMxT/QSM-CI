# χ-sepnet

The SNU-LIST χ-separation network: a 3D U-Net that maps QSM, local field and R2′ to paramagnetic
(χ+) and diamagnetic (χ−) source maps, run by the authors' route — `chi_sepnet_general` of the
χ-separation toolbox v1.1.3 — on CPU via `onnxruntime`.

- **Stage:** `chi-separation` (localfield, r2prime, mask, params → chi-para, chi-dia; ppm)
- **Engine:** the toolbox's ONNX graphs + `recon.py` / `chisep_route.py`; see [BUILD.md](BUILD.md)
- **Reference:** Kim et al., Hum Brain Mapp 2025 (χ-sepnet) · doi:[10.1002/hbm.70136](https://doi.org/10.1002/hbm.70136);
  Shin et al., NeuroImage 2021 (χ-separation) · doi:[10.1016/j.neuroimage.2021.118371](https://doi.org/10.1016/j.neuroimage.2021.118371)
- **Licence:** academic use; the networks and their normalisation statistics come via the SNU-LIST
  Google Form and are baked into the image, not redistributed here.

## Route (recovered from the toolbox's P-code by black-box probing; astewartau/QSM.rs#377)

- The local field, R2′ and mask are rotated into the training frame (B0 along the third axis) and
  resampled onto a centred 1 mm grid padded to multiples of 16 (`interp3 'spline'`; the mask
  `'linear'` > 0.5).
- The QSM channel is the toolbox's own QSMnetME there (see `../qsmnetme`); the stage's `chimap` is
  not read.
- Channels `[QSM, local field, R2′ / Dr]`, each z-scored with the training-set statistics in
  `xsepnet_train_patch_norm_factor_*.mat`, 0 outside the mask; **Dr = 114 Hz/ppm**, the model's
  training assumption, deliberately *not* retuned to the phantom's relaxivity.
- The whole frame in one pass; `χ± = max(std·y + mean, 0)`; both mapped back onto the acquired grid
  (`interp3 'spline'`), set to 0 where negative and outside the mask.
- χ− is written as a positive magnitude, the convention used throughout QSM-CI.

The first version of this entry fed the stage's χ map as the QSM channel and ran the network alone
on the acquired grid in 192×192×128 sliding-window patches.
