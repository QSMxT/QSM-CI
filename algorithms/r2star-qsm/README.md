# R2\*-QSM (Dimov et al. 2022)

Susceptibility source separation from gradient-echo data alone: R2\* is fit from the multi-echo
magnitude and combined with the provided χ_total under a single-relaxometric-constant model,
R2\* = 𝓇·(|χ+| + |χ−|) with χ_total = χ+ + χ−, solved per voxel in closed form
(χ+ = (χ_total + R2\*/𝓇)/2, |χ−| = (R2\*/𝓇 − χ_total)/2) with χ+ ≥ 0, χ− ≤ 0 enforced by
clipping. No separate R2/R2′ measurement is needed — the trade-off is that R2\* carries the
irreversible tissue-R2 baseline, which the single constant absorbs (Dimov's empirical
𝓇 = 274 Hz/ppm at 3 T, field-scaled here as 274·B0/3 — the method's own assumption, not a fit to
the phantom). This reference implementation is the paper's voxel-level solve; the full method's
field data-consistency term (auto-satisfied when χ_total is provided) and edge-masked L1
regularisation are omitted.

- **Stage:** `chi-separation` — reads `magnitude` (multi-echo), `chimap` (χ_total), `mask`,
  `params` (TE, B0); writes `chi-para.nii.gz` (χ+) and `chi-dia.nii.gz` (χ−), ppm
- **Engine:** Python (`recon.py`), CPU — no weights, no network
- **Reference:** Dimov et al., *J Neuroimaging* 2022 ·
  doi:[10.1111/jon.13014](https://doi.org/10.1111/jon.13014) (and *Tomography*
  2022;8(3):1544-1551); R2\* susceptibility model: Yablonskiy & Haacke, *MRM* 1994
- **Image:** `ghcr.io/astewartau/qsm-ci/r2star-qsm:v1`, built from this folder's `Dockerfile`
  (`python:3.12-slim` + numpy/scipy/nibabel, `recon.py` and `run.sh` baked at `/opt/qsm-ci`; the
  folder can also be mounted over it).

## How QSM-CI runs it

`run.sh` calls `python3 recon.py <input-dir> <output-dir>`. A χ-separation method produces two
files, so `-o` is a directory:

```bash
qsm-ci run r2star-qsm --magnitude magnitude.nii.gz --chimap chimap.nii.gz --mask mask.nii.gz --params params.json -o out/
```
