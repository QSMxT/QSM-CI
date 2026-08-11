# Building the hc-chisep image

hc-chisep is fully self-contained: `recon.py` vendors the handful of hollow-cylinder model
functions it needs (ported from qsm-forward, which implements Wharton & Bowtell, PNAS 2012,
doi:10.1073/pnas.1211075109) and only depends on `numpy`, `scipy`, `nibabel`. No MATLAB, no GPU,
no pretrained weights, no network access at run time.

## Build + push

Create a `Dockerfile` in this directory:

```dockerfile
FROM python:3.11-slim
RUN pip install --no-cache-dir numpy scipy nibabel
COPY recon.py run.sh /app/
WORKDIR /app
ENTRYPOINT ["bash", "run.sh"]
```

```bash
docker build -t ghcr.io/astewartau/qsm-ci/hc-chisep:v1 algorithms/hc-chisep
docker push  ghcr.io/astewartau/qsm-ci/hc-chisep:v1   # make the GHCR package public
```

## Smoke test (local runner, no docker)

```bash
HCCHISEP_PYTHON=/path/to/python-with-numpy-scipy-nibabel \
bash algorithms/hc-chisep/run.sh data/sim/chisep-ship/inputs /tmp/hc-chisep-out
```

Runs in ~2 minutes full brain (1.3 M voxels, 8 echoes) on 14 CPU cores. Modes via
`HCCHISEP_MODE` = `headline` (default, signal-derived orientation) | `dti` (θ from the
optional `fiber_angle.nii.gz` input — comparison arm) | `closed-form` (ablation).
`HCCHISEP_DIAG=1` additionally writes `theta.nii.gz`, `mwf.nii.gz`, `beat_weight.nii.gz`.

## What it expects

- `chimap.nii.gz` (χ_total, ppm), `r2prime.nii.gz` (Hz), `magnitude.nii.gz` (4D multi-echo GRE),
  `mask.nii.gz`, `params.json` (keys `TE` [s], `B0` [T]; optional `se_TE`).
- Optional: `se_magnitude.nii.gz` (4D multi-echo SE; used as soft MWF evidence when present).
- Optional: `fiber_angle.nii.gz` — read ONLY in `dti` mode; the headline mode derives
  orientation from the GRE signal itself.
- Outputs: `chi-para.nii.gz` (χ+ ≥ 0) and `chi-dia.nii.gz` (|χ−| ≥ 0, positive magnitude).
