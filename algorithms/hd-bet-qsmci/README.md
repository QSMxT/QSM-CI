# HD-BET brain extraction

A brain mask from the multi-echo GRE magnitude with the HD-BET CNN (Isensee et al., *Hum Brain
Mapp* 2019). `extract.py` combines the echoes by root-sum-of-squares (a higher-SNR image than any
single echo), runs HD-BET on CPU (`QSMCI_GPU=1` for CUDA) and writes a 0/1 `uint8` mask on the
magnitude's grid.

An optional **signal-gated erosion** — off by default (`erode_threshold: 0`) — then strips only
boundary voxels whose signal is low (skull-base / sinus T2\* dropout) after dividing the
receive-coil bias field out of the RSS, never deeper than `erode_depth_cap` voxels below the original
surface. `0.8` is the harmonization-track setting. The parameters and the reasoning behind each are
documented in `algorithm.yml`.

- **Stage:** `brain-extraction` — reads `magnitude` (multi-echo) (+ `params`); writes
  `mask.nii.gz`. Isolated-only: `mask` is not a scored artifact, so this never enters the composed
  matrix — it exists to generate masks for datasets that ship without one.
- **Engine:** Python; CPU-build PyTorch + the `HD-BET` package. The model weights are fetched at
  image-build time and baked in (there is no network at run time).
- **Reference:** Isensee et al., *Hum Brain Mapp* 2019 ·
  doi:[10.1002/hbm.24750](https://doi.org/10.1002/hbm.24750) · code:
  https://github.com/MIC-DKFZ/HD-BET (Apache-2.0)
- **Image:** `ghcr.io/astewartau/qsm-ci/hd-bet:v1`, built from this folder's `Dockerfile` on the
  shared `py-ref` base ([`algorithms/_base`](../_base)).

## How QSM-CI runs it

`run.sh` forces `HOME=/opt/hdbet` — where the baked weights live; apptainer would otherwise
override `HOME` to the host's and HD-BET would try to re-download them — then calls
`python3 extract.py <input-dir> <output-dir>`.

```bash
qsm-ci run hd-bet-qsmci --magnitude magnitude.nii.gz -o mask.nii.gz
qsm-ci run hd-bet-qsmci --magnitude magnitude.nii.gz --set erode_threshold=0.8 -o mask.nii.gz
```
