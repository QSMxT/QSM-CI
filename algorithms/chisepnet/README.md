# χ-sepnet

The SNU-LIST χ-separation network: a 3D U-Net that maps QSM, local field and R2′ (or R2*) to
paramagnetic (χ+) and diamagnetic (χ−) source maps. Runs the authors' trained ONNX model on CPU via
`onnxruntime`.

- **Stage:** `chi-separation` (localfield, r2prime, chimap, mask → chi-para, chi-dia; ppm)
- **Engine:** ONNX model + `recon.py`; see [BUILD.md](BUILD.md)
- **Reference:** Shin et al., NeuroImage 2021 · doi:[10.1016/j.neuroimage.2021.118371](https://doi.org/10.1016/j.neuroimage.2021.118371)
- **Licence:** academic use; the model and its normalisation statistics come via the SNU-LIST Google
  Form and are baked into the image, not redistributed here.

## Preprocessing (reverse-engineered from the toolbox, validated against it)

- Input channels, in order: `[QSM, local field, R2′ / Dr]`, each z-scored with the training-set
  statistics shipped in `xsepnet_train_patch_norm_factor_*.mat`.
- Field and χ in ppm; R2′ divided by the network's own relaxivity, **Dr = 114 Hz/ppm**. That value
  is the model's training assumption and is deliberately *not* retuned to the phantom's relaxivity:
  the mismatch is a real, informative model error, the same one it would carry on any other data.
- Inference on 192³ sliding-window patches.
- χ− is written as a positive magnitude, the convention used throughout QSM-CI.
