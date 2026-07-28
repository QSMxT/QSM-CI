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

R2′ is physically realistic: `R2' = Dr₊·|χ+| + Dr₋·|χ−|` with **split relaxivities `Dr₊ = 114`,
`Dr₋ = 30 Hz/ppm`** (qsm-forward defaults; paramagnetic iron dephases more per ppm than diamagnetic
myelin/calcium). This is what real tissue looks like and what learned methods (χ-sepnet) are trained on,
so it's the right ground truth; each method applies its own Dr assumption when inverting.

Note: purely analytic single-Dr methods (e.g. iLSQR) are disadvantaged by split relaxivities, which is a
fair reflection of a real limitation — but that is *not* why our iLSQR run failed (it produced pure
artifact regardless of the R2′ model, a separate wiring/black-box issue; χ-sepnet works well here).

To rebuild `r2prime.nii.gz` from the ground-truth sources:
`114·|chi-para| + 30·|chi-dia|` within the brain mask.
