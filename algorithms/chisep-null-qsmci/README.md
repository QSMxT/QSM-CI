# chisep-null (closed-form null baseline)

The analytic null baseline for the χ-separation stage. Per voxel it solves the benchmark's own two
source-model equations — χ+ + χ− = χ_total and Dr+·χ+ + Dr−·|χ−| = R2′ — exactly from the two
provided inputs. No dipole inversion, no regularisation, no learning: a few array operations. On an
isotropic single-kernel phantom it inverts the phantom's own arithmetic and is exact; where the
tissue physics departs from that model (multi-compartment, orientation-dependent white-matter R2′)
it fails in a structured way. Its score is the benchmark's honest floor — a real method demonstrates
separation skill only by beating it.

Relaxivities are field-scaled literature values: Dr+ = 137·B0/3 Hz/ppm (Shin et al. 2021) and
Dr− = Dr+ × 133.77/107.84, the Yablonskiy–Haacke cylinder/sphere static-dephasing ratio.

- **Stage:** `chi-separation` — reads `chimap` (χ_total), `r2prime`, `mask`, `params` (B0);
  writes `chi-para.nii.gz` (χ+) and `chi-dia.nii.gz` (χ−), ppm
- **Engine:** Python (`recon.py`, numpy/scipy/nibabel), CPU
- **Reference:** none of its own — the model equations it inverts are cited in `recon.py`. Its
  counterpart for the region-disjoint Ridani phantoms is `ridani-null-qsmci`.
- **Image:** `ghcr.io/astewartau/qsm-ci/chisep-null-qsmci:v1`, built from this folder's
  `Dockerfile` (`python:3.12-slim` + numpy/scipy/nibabel, `recon.py` and `run.sh` baked at
  `/opt/qsm-ci`; the folder can also be mounted over it).

## How QSM-CI runs it

`run.sh` calls `python3 recon.py <input-dir> <output-dir>`. A χ-separation method produces two
files, so `-o` is a directory:

```bash
qsm-ci run chisep-null-qsmci --chimap chimap.nii.gz --r2prime r2prime.nii.gz --mask mask.nii.gz --params params.json -o out/
```
