# BFRnet (ONNX)

Deep-learning background field removal — a 3D dual-frequency octave-convolution U-net (Zhu et al.,
*Z Med Phys* 2022) that predicts the background field from the total field; the local tissue field is
`total − background`, masked. Everything in ppm.

- **Stage:** `bfr` (totalfield → localfield, ppm)
- **Engine:** ONNX Runtime (CPU). The authors' MATLAB network (`BFRnet.mat`) is exported to ONNX and
  run without MATLAB — output matches MATLAB `predict` to ~1e-8, at ~1.5 GB RAM and a ~0.4 GB image.
  This replaces the former compiled-MATLAB/MCR submission (which OOM-ed on the 16 GB hosted runner).
- **Reference:** Zhu et al., *Z Med Phys* 2022 · doi:[10.1016/j.zemedi.2022.08.001](https://doi.org/10.1016/j.zemedi.2022.08.001) · code: https://github.com/sunhongfu/BFRnet

See `BUILD.md` for how `BFRnet.onnx` is produced and how to build/push the image.
