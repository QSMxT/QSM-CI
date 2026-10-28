# WaveSep (QSM.rs)

WaveSep (Fang et al., MLCN 2023) as the Rust implementation in QSM.rs that QSMxT exposes as
`qsmxt separate wavesep`. It splits χ_total into paramagnetic (χ+) and diamagnetic (χ−) sources
under two voxel-wise fidelity terms (χ+ + χ− ≈ χ_total, χ+ − χ− ≈ R2′/Dr) and a wavelet-domain L1
prior (db4, maximum level), solved by proximal gradient with the authors' defaults.

- **Stage:** `chi-separation`: reads `chimap` (χ_total, ppm), `r2prime` (Hz), `mask`, `params`;
  writes `chi-para.nii.gz` (χ+ ≥ 0) and `chi-dia.nii.gz` (|χ−|), both ppm.
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs), `src/separation/wavesep.rs`.
- **Original:** [`wavesep`](../wavesep) runs the authors' Python solver; the two entries share
  `algorithm: wavesep`, so they form a port parity pair (docs/parity.md).
- **Dr:** 137 Hz/ppm for both sources, as the `wavesep` entry (`--set Dr=…`).
- **Reference:** Fang, Shin, van Zijl, Li, Sulam, MLCN 2023 ·
  doi:[10.1007/978-3-031-44858-4_6](https://doi.org/10.1007/978-3-031-44858-4_6).
