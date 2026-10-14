# HEIDI

**Homogeneity Enabled Incremental Dipole Inversion.** HEIDI splits k-space at the dipole cone and
treats the two halves differently:

- **Well-conditioned coefficients** (`|D(k)| > cone_threshold`) are taken unchanged from an already
  computed χ map — here the minimally regularised [LSQR](../lsqr-qsmrs) solution — and held as
  *exact* constraints.
- **Ill-conditioned coefficients inside the cone**, where direct division amplifies noise without
  bound, are recovered by minimising a weighted total variation subject to those constraints:

```
minimise  Σ_v ‖ (Mx ∂x χ, My ∂y χ, Mz ∂z χ) ‖   subject to   (F χ)|cone = (F χ_init)|cone
```

The "homogeneity" of the name is the weighting `M`. Each gradient direction gets its own mask, built
by thresholding the gradient of the **field** map: where the field is locally flat the susceptibility
is expected to be flat too and TV is applied; across an anatomical edge the mask opens and the
gradient goes unpenalised. A Laplacian test additionally opens the mask where the field curves
sharply. The constrained problem is solved with NESTA — the TV term is smoothed by a parameter μ that
is annealed down over several continuation steps.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Schweser et al., NeuroImage 2012 ([10.1016/j.neuroimage.2012.05.067](https://doi.org/10.1016/j.neuroimage.2012.05.067))

## How QSM-CI runs it

```bash
qsmxt invert heidi /input/localfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz \
  --b0-direction <B0_dir> --b0 <B0> [--magnitude /input/magnitude.nii.gz]
```

The LSQR seed is run with its output **unmasked**, because HEIDI low-passes χ through the dipole cone
and a hard mask edge rings. That is qsmxt's own arrangement for HEIDI, not a QSM-CI choice.

## Parameters

| parameter | default | description |
|---|---|---|
| `cone_threshold` | 0.1 | `|D(k)|` above which a coefficient is kept from the LSQR seed |
| `gradient_threshold` | 3925.2 | field-gradient threshold (ppm/mm) below which a direction reads as homogeneous |
| `gradient_mask_floor` | 0.1 | TV weight kept where every direction reads as an edge (`0` = upstream's binarised masks) |
| `continuation_steps` | 8 | NESTA continuation steps on μ — the dominant quality knob, and more is not better |
| `inner_iterations` | 500 | accelerated-gradient iterations per continuation step |
| `tol` | 1e-3 | relative objective change that ends an inner loop early |
| `lsqr_residual_weighting` | field-scaled | residual-field weight of the LSQR seed |
| `lsqr_max_iter` | 400 | LSQR seed iterations |

## Units

Field thresholds are in ppm/mm and ppm/voxel², independent of echo time and field strength. Upstream
expresses the same numbers in units of phase/(TE·B0); the defaults above are those values converted.
