# χ-separation, MEDI (QSM.rs)

The SNU χ-separation toolbox's `chi_sep_MEDI` (v1.1.3) as the Rust port in QSM.rs that QSMxT
exposes as `qsmxt separate chi-sep-medi`. It is a Gauss-Newton solve for χ+ and |χ−| from the local
field and R2′, with MEDI's edge-masked L1 regulariser, started from χ_total.

- **Stage:** `chi-separation`. It reads `localfield` (ppm), `r2prime` (Hz), `chimap` (χ_total,
  ppm), `magnitude` (every echo), `mask` and `params`. It writes `chi-para.nii.gz` (χ+ ≥ 0) and
  `chi-dia.nii.gz` (|χ−|), both in ppm.
- **Inputs, as [`chisep-medi`](../chisep-medi):**
  - N_std is MEDI `Fit_ppm_complex`'s noise map from the echoes' magnitudes;
  - the edge mask comes from their root-sum-of-squares;
  - there is no CSF term (`csf_mask=none`; the stage contract has no CSF mask). `--set
    csf_mask=r2star` uses the CSF mask from ARLO R2*, as the toolbox's script makes it.
- **Run:** `qsm-ci run chisep-medi-qsmrs` with the shared qsmxt image (`image:` in
  `algorithm.yml`; no image of its own). `csf_mask=none` needs a qsmxt with
  `separate chi-sep-medi --csf-mask` (QSMxT/QSMxT#472).
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs), `src/separation/chi_sep_medi.rs`.
- **Original:** [`chisep-medi`](../chisep-medi) runs the toolbox. The two entries form the parity
  pair `chisep-medi` (docs/parity.md).
- **Reference:** Shin et al., NeuroImage 2021 ·
  doi:[10.1016/j.neuroimage.2021.118371](https://doi.org/10.1016/j.neuroimage.2021.118371).
