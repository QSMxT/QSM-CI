# R2′ = f·R2\* (fixed-fraction R2′ generation)

The cheapest R2′ substitute for the GRE-only condition: fit R2\* from the multi-echo GRE magnitude
(weighted log-linear least squares) and scale it, R2′ = f·R2\*, with the literature f = 0.52
(attributed to Dimov et al.; evaluated in Ji et al., *NMR Biomed* 2024 and Oliveira Assunção et al.,
*MRM* 2026, both of which document the χ-separation error a fixed fraction propagates). Its composed
combinations with each R2′-consuming χ-separation method put a number on what that shortcut costs,
against the same methods fed the true R2′. The tuned `fraction` values in `algorithm.yml` are each
phantom's best *fixed* fraction — the ceiling of any global scaling there.

- **Stage:** `r2prime-generation` — reads `magnitude` (multi-echo), `mask`, `params` (TE); writes
  `r2prime.nii.gz` (Hz)
- **Engine:** Python (`recon.py`), CPU
- **Reference:** Ji et al., *NMR Biomed* 2024;37(9):e5167 ·
  doi:[10.1002/nbm.5167](https://doi.org/10.1002/nbm.5167) (evaluates the 0.52 rule this implements)
- **Image:** `ghcr.io/astewartau/qsm-ci/r2prime-scaled-qsmci:v1`, built from this folder's
  `Dockerfile` (`python:3.12-slim` + numpy/nibabel, `recon.py` and `run.sh` baked at
  `/opt/qsm-ci`; the folder can also be mounted over it).

## How QSM-CI runs it

`run.sh` calls `python3 recon.py <input-dir> <output-dir>`.

```bash
qsm-ci run r2prime-scaled-qsmci --magnitude magnitude.nii.gz --mask mask.nii.gz --params params.json -o r2prime.nii.gz
qsm-ci run r2prime-scaled-qsmci … --set fraction=0.6
```

## Parameters

| parameter | default | description |
|---|---|---|
| `fraction` | 0.52 | the R2′/R2\* scaling; per-phantom tuned values in `algorithm.yml` |
