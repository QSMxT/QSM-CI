# QSMnetME

The QSM network of the SNU-LIST χ-separation toolbox v1.1.3 (`models/240904_QSMnet.onnx`), trained
on multi-echo data (Kim et al., χ-sepnet, Hum Brain Mapp 2025). The toolbox runs it inside
`chi_sepnet_general` to make χ-sepnet's QSM channel; this entry runs that step on its own.

- **Stage:** `dipole` (localfield, mask, params → chimap; ppm)
- **Engine:** the toolbox's ONNX graph + `recon.py` / `chisep_route.py` (shared with `chisepnet`);
  image recipe in [../chisepnet/BUILD.md](../chisepnet/BUILD.md)
- **Reference:** Kim et al., Hum Brain Mapp 2025 · doi:[10.1002/hbm.70136](https://doi.org/10.1002/hbm.70136)
- **Licence:** academic use; the networks and their normalisation statistics come via the SNU-LIST
  Google Form and are baked into the image, not redistributed here.

## Route (`chi_sepnet_general`, recovered from the toolbox's P-code)

1. The local field (Hz) is rotated into the training frame (B0 along the third axis) and resampled
   onto a centred 1 mm grid padded to multiples of 16, with `interp3 'spline'`; the mask with
   `'linear'` > 0.5.
2. `(field / (CF·1e-6) − field_mean) / field_std` (the χ-sepnet normalisation file's field
   statistics), 0 outside the mask; the whole frame in one pass.
3. `χ = cosmos_sus_std·y + cosmos_sus_mean`, masked; mapped back onto the acquired grid with
   `interp3 'spline'` and masked.

Details and the probing method: `chisep_route.py`, and astewartau/QSM.rs#377.
