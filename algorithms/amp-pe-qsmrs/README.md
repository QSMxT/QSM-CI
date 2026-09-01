# AMP-PE (QSM.rs)

Approximate Message Passing with Parameter Estimation: a probabilistic Bayesian dipole inversion.
MAP estimation over the nonlinear complex-exponential forward model with a Laplace sparse-wavelet
prior and a two-component Gaussian-mixture noise model, with all distribution parameters estimated
automatically (tuning-free).

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Huang et al., Magn Reson Med 2023;90(4):1414-1430 · doi:[10.1002/mrm.29722](https://doi.org/10.1002/mrm.29722)

The Rust port has been verified against the original MATLAB
([EmoryCN2L/QSM_AMP_PE](https://github.com/EmoryCN2L/QSM_AMP_PE)) to nrmse ~1e-6 / corr ~1.0 on
matched inputs (db1/db2, nlevel 2/3, with/without magnitude, up to the full two-stage solve). A
separate MATLAB-compiled submission (`amp-pe`) runs the reference code directly.

## How QSM-CI runs it

```bash
qsmxt invert amp-pe /input/localfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz \
  --b0-direction <B0> --b0 <field-strength> [--magnitude /input/magnitude.nii.gz]
```

Magnitude is an optional input: when present it weights the data term and builds a wavelet morphology
mask that injects anatomical edges into the prior; without it the method runs with uniform weights
and no morphology mask.

## Parameters

| parameter | default | description |
|---|---|---|
| `wave_order` | 1 | Daubechies wavelet order (1=db1, best for straight B0; 2=db2 for oblique acquisitions) |
| `nlevel` | 3 | number of levels in the 3D wavelet transform |
| `wave_pec` | 0.85 | fraction of magnitude wavelet coefficients kept in the morphology mask (anatomical prior) |
| `simulated_te` | 0.008 | echo time (s) used to simulate the phase from the local field |
| `max_linearization_ite` | 25 | linearization steps per reconstruction stage (preliminary and final) |
| `damp_rate_sig` | 0.01 | AMP signal-update damping (0-1) |
| `damp_rate_par` | 0.1 | AMP parameter-estimation (kappa) damping (0-1) |

_Citations/DOIs are auto-generated best-effort references and should be verified._
