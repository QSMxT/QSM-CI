# Complex fit + ROMEO (QSM.rs)

MEDI's field map as QSM.rs ports it: the magnitude-weighted fit of the complex echoes
(`Fit_ppm_complex`, MEDI toolbox 2024.11.26), unwrapped spatially with ROMEO, through
`qsmxt fieldmap romeo --b0-estimation complex-fit`. QSM.rs does not port MEDI's region-growing
`unwrapPhase`, so the total field is not like for like with `fit-ppm-complex-cornell`'s; the pair
compares the steps that are ported:

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
- **Image:** the shared QSMxT engine image ([`algorithms/_qsmxt`](../_qsmxt)). `ci_skip` until a
  qsmxt release has `--complex-fit-output` (QSMxT/QSMxT#462); the parity workflow runs it against a
  qsmxt build.
