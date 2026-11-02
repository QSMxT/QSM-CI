# χ-separation, iLSQR (QSM.rs)

The SNU χ-separation toolbox's `chi_sep_iLSQR` (v1.1.3) as the Rust port in QSM.rs that QSMxT
exposes as `qsmxt separate chi-sep-ilsqr`. It is an iLSQR-style solve for χ+ and |χ−| (LSQR, then
streaking removal, then NNLS) from the local field and R2′, started from a QSM.

- **Stage:** `chi-separation`. It reads `localfield` (ppm), `r2prime` (Hz), `mask` and `params`,
  plus `chimap` with `qsm=chimap`. It writes `chi-para.nii.gz` (χ+ ≥ 0) and `chi-dia.nii.gz`
  (|χ−|), both in ppm.
- **QSM:** as [`chisep-ilsqr`](../chisep-ilsqr) and the toolbox's `Chisep_script.m`, the QSM comes
  from iLSQR on the local field (`qsmxt invert ilsqr`, QSM.rs's port of STI Suite's `QSM_iLSQR`,
  12 mm padding). `--set qsm=chimap` uses the given χ_total instead.
- **Run:** `qsm-ci run chisep-ilsqr-qsmrs` with the shared qsmxt image (`image:` in
  `algorithm.yml`; no image of its own).
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs), `src/separation/chi_sep_ilsqr.rs`.
- **Original:** [`chisep-ilsqr`](../chisep-ilsqr) runs the toolbox. The two entries form the parity
  pair `chisep-ilsqr` (docs/parity.md), which feeds the port the original's own QSM.
- **Reference:** Shin et al., NeuroImage 2021 ·
  doi:[10.1016/j.neuroimage.2021.118371](https://doi.org/10.1016/j.neuroimage.2021.118371).
