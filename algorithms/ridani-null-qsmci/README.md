# ridani-null (region-disjoint closed-form null baseline)

The analytic null baseline for the Ridani et al. (2026) phantom family. Where `chisep-null-qsmci`
inverts a co-located single-kernel model (Dr+ and Dr− act in every voxel), this inverts the
region-disjoint, theoretical field-scaled forward model those phantoms are actually built from:
outside white matter only a paramagnetic relaxivity acts (Dr+ = (2π)²·γ̄·B0/(9√3) ≈ 107.84·B0
Hz/ppm, so χ+ = R2′/Dr+ and |χ−| = χ+ − χ_total); inside white matter only a diamagnetic one
(Dr−(θ) ≈ 133.77·B0·sin²θ, applied as a field-scaled constant because fibre orientation is not an
input, so |χ−| = R2′/Dr− and χ+ = χ_total + |χ−|). On the isotropic phantom it is exact; on the
anisotropic phantoms it mis-estimates WM χ− by exactly the orientation modulation the benchmark
measures. Its score is that dataset family's floor — a real method demonstrates separation skill
only by beating it without the held-out segmentation.

- **Stage:** `chi-separation` — reads `chimap` (χ_total), `r2prime`, `mask`, `params` (B0), plus
  `dseg.nii.gz` from the input directory *if present* (white matter = label 8). Without a `dseg`
  it falls back to the co-located single-kernel model (logged as such). Writes `chi-para.nii.gz`
  (χ+) and `chi-dia.nii.gz` (χ−), ppm.
- **Engine:** Python (`recon.py`), CPU
- **Reference:** forward model — Ridani, De Leener, Alonso-Ortiz, *Magn Reson Med* 2026 ·
  doi:[10.1002/mrm.70468](https://doi.org/10.1002/mrm.70468); relaxivities — Yablonskiy & Haacke,
  *Magn Reson Med* 1994 · doi:[10.1002/mrm.1910320610](https://doi.org/10.1002/mrm.1910320610)
- **Image:** `ghcr.io/astewartau/qsm-ci/ridani-null-qsmci:v1`, built from this folder's
  `Dockerfile` (`python:3.12-slim` + numpy/scipy/nibabel, `recon.py` and `run.sh` baked at
  `/opt/qsm-ci`; the folder can also be mounted over it).

## How QSM-CI runs it

`run.sh` calls `python3 recon.py <input-dir> <output-dir>`. It is meant for the `ridani-*`
phantoms (registry keys in `scripts/datasets.json`). A χ-separation method produces two files, so
`-o` is a directory; `dseg` is not a stage artifact, so `qsm-ci run` has no flag for it — a run
without one exercises the co-located fallback.

```bash
qsm-ci run ridani-null-qsmci --chimap chimap.nii.gz --r2prime r2prime.nii.gz --mask mask.nii.gz --params params.json -o out/
```
