# NDI — Nonlinear Dipole Inversion (MATLAB)

**STATUS: scaffold — needs image build (MATLAB Compiler license required).** Source is complete;
the compiled `recon` binary and pushed image are the human's job (see `BUILD.md`).

## What it does
Nonlinear Dipole Inversion (Polak/Bilgic et al., *NMR Biomed* 2020, doi:10.1002/nbm.4271) — a
gradient-descent QSM solver with a nonlinear data-fidelity term, promoted as essentially
**parameter-tuning-free**. Implementation is `ndi.m` from Carlos Milovic's **FANSI toolbox**.

- **Stage:** `dipole` — consumes `localfield` (ppm), `mask`, `params`; produces `chimap` (ppm).

## Units handling
`ndi.m` uses a `sin(phi - phase)` data term, so the input must be in **radians**. `recon.m` converts
`phase_rad = field * 2*pi * 42.58 * B0 * TE`, runs `ndi`, then divides the output by the same
`phs_scale` to return **ppm** (the `ndi.m` header states input and output are both in radians).

## Parameters (defaults = FANSI ndi.m defaults; NDI is designed to be tuning-free)
| name | default | meaning |
|------|---------|---------|
| `tau` | 2.0 | gradient-descent step size |
| `iterations` | 100 | gradient-descent iterations |
| `alpha` | 1e-5 | small Tikhonov stabiliser |

## Assumptions the human must verify
- **Image is SHARED** with `fansi`, `l1-qsm`, `wh-qsm`: `ghcr.io/astewartau/qsm-ci/fansi:v1`
  (see `BUILD.md`).
- **DOI 10.1002/nbm.4271** is the NDI paper (Polak et al., *NMR Biomed* 2020); confirm before merge.
- **`tau=2.0`** is `ndi.m`'s slightly-accelerated default; on the QSM-CI phantom's extreme sources it
  could diverge. If so, drop `tau` toward 1.0 (the `ndi_auto.m` default) — verify on the phantom.
- **Weighting:** binary mask (no magnitude at the dipole stage).
- **GPU disabled** — scoring Runtime is CPU-only.
- **License:** FANSI ships no LICENSE file (README: "academic and research" use, BSD-style
  disclaimer) → `license: academic use; cite paper`.
