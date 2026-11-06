# Complex fit + ROMEO (QSM.rs)

MEDI's field map as QSM.rs ports it: the magnitude-weighted fit of the complex echoes
(`Fit_ppm_complex`, MEDI toolbox 2024.11.26), unwrapped spatially, through
`qsmxt fieldmap <unwrapping> --b0-estimation complex-fit`. The `unwrapping` parameter picks the
unwrapper: `romeo` (QSMxT's default) or `medi-region-growing`, QSM.rs's port of MEDI's
region-growing `unwrapPhase`, which makes the total field MEDI's own. The parity pair with
`fit-ppm-complex-cornell` runs `medi-region-growing` and compares the total field and these
intermediates:

| intermediate | what | units |
|---|---|---|
| `ifreq_raw` | the fit before unwrapping: phase accrued per echo spacing, wrapped | rad per echo spacing |
| `n_std` | its standard deviation (MEDI's `N_std`) | rad per echo spacing |
| `r2star` | ARLO's R2* (`qsmxt r2star`), 3+ echoes | Hz |

- **Stage:** `field-mapping` — reads `phase` (multi-echo), `magnitude`, `mask`, `params`; writes
  `totalfield.nii.gz` (ppm)
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs) (Rust), CPU
- **Reference:** Liu et al., *Magn Reson Med* 2013 ·
  doi:[10.1002/mrm.24272](https://doi.org/10.1002/mrm.24272)
- **Image:** `ghcr.io/astewartau/qsm-ci/qsmxt:v11.0.0`, the shared QSMxT engine image ([`algorithms/_qsmxt`](../_qsmxt)).
