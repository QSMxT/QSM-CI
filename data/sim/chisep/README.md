# χ-separation phantom (qsm-forward)

Susceptibility source-separation dataset: methods are fed the local field, R2′, χ_total and
multi-echo magnitude, and must recover the paramagnetic (χ+) and diamagnetic (χ−) source maps.

## Layout

- `inputs/` — provided to the method: `localfield.nii.gz` (ppm), `r2prime.nii.gz` (Hz),
  `chimap.nii.gz` (χ_total, ppm), `magnitude.nii.gz` + `phase.nii.gz` (4D multi-echo GRE),
  `mask.nii.gz`, `params.json`. Field-based methods (χ-sepnet, SUSEP-Net) use local field + R2′ + QSM;
  GRE-based methods (APART-QSM, DECOMPOSE) opt into the raw multi-echo `phase`/`magnitude` and do their
  own field mapping / QSM.
- `groundtruth/` — scored against: `chi-para.nii.gz` (χ+), `chi-dia.nii.gz` (χ−, stored as a positive
  magnitude), plus `chimap.nii.gz` and `dseg.nii.gz`.

## R2′ relaxivity model

R2′ uses a **single magnitude decay kernel** `Dr = 137 Hz/ppm` shared by both source types:

```
R2' = Dr · (|χ+| + |χ−|),   Dr = 137 Hz/ppm
```

This is the standard chi-separation model (Shin et al. 2021): in the static-dephasing regime the
reversible relaxation depends on the *magnitude* of the field perturbation, not its sign, so one kernel
applies to iron and myelin alike. 137 Hz/ppm is Shin's empirically measured value (multi-orientation
work, 2022); every published chi-separation method we benchmark (χ-sep iLSQR/MEDI, χ-sepnet, SUSEP-Net,
APART-QSM, WaveSep) is built on this single-kernel assumption.

**Why not a split (`Dr₊ ≠ Dr₋`)?** Real microstructure (spherical ferritin vs anisotropic myelin)
plausibly gives the two source types different *effective* relaxivities, so a split is biophysically
defensible in principle. But it is **deliberately not used here**, because: (a) the relaxivities are
**not recoverable from the data** — with one QSM + one R2′ map they must be assumed a priori, so baking a
specific split into the ground truth mainly rewards whichever method happens to share that exact
assumption rather than testing recovery; (b) no widely-used chi-sep method or reference phantom adopts a
split; and (c) the split this phantom previously shipped (`Dr₊ = 114`, `Dr₋ = 30`) had **no published
basis** — 114 is a valid *single*-kernel value (COSMOS-referenced, χ-sepnet), but the `30` was
unsourced. A split remains available as an explicit opt-in in qsm-forward (`generate_r2prime(..., dr_neg=…)`
or `--dr-neg`) for sensitivity studies. See the `DR_KERNEL` note in `qsm-forward` for the full rationale.

To rebuild `r2prime.nii.gz` from the ground-truth sources:
`137·(|chi-para| + |chi-dia|)` within the brain mask.
