# L1-QSM — L1-norm data-fidelity QSM (MATLAB)

**STATUS: scaffold — needs image build (MATLAB Compiler license required).** Source is complete;
the compiled `recon` binary and pushed image are the human's job (see `BUILD.md`).

## What it does
L1-norm data-fidelity QSM, a.k.a. PI-QSM (Milovic et al., *MRM* 2022,
doi:10.1002/mrm.28957). A nonlinear dipole inversion whose **L1 data-fidelity term** is more robust
to phase inconsistencies / streaking than the standard L2 (FANSI) term, with TV regularization.
Implementation is `nlL1TV.m` from Carlos Milovic's **FANSI toolbox**.

- **Stage:** `dipole` — consumes `localfield` (ppm), `mask`, `params`; produces `chimap` (ppm).

## Units handling
`nlL1TV.m` forms `exp(1i*input)`, so the input must be in **radians**. `recon.m` converts
`phase_rad = field * 2*pi * 42.58 * B0 * TE`, runs `nlL1TV`, then divides the output by the same
`phs_scale` to return **ppm**.

## Parameters (defaults track FANSI recommendations)
| name | default | meaning |
|------|---------|---------|
| `alpha1` | 3e-4 | gradient L1 (TV) penalty |
| `lambda` | 1.0 | L1 data-fidelity strength (scales the fidelity weight); <1 rejects more inconsistent voxels |
| `mu1` | 3e-2 | gradient-consistency ADMM weight (= 100·alpha1) |
| `iterations` | 50 | max ADMM outer iterations |
| `tol_update` | 1.0 | convergence threshold (percent update) |

## Assumptions the human must verify
- **Image is SHARED** with `fansi`, `ndi`, `wh-qsm`: `ghcr.io/astewartau/qsm-ci/fansi:v1`
  (see `BUILD.md`).
- **DOI 10.1002/mrm.28957** — "Streaking artifact suppression of QSM reconstructions via L1-norm
  data fidelity optimization (L1-QSM)", Milovic et al. Confirmed via Crossref.
- **`lambda` default = 1.0** (no extra phase rejection). The FANSI docstring recommends `lambda*mask`
  with the magnitude in [0,1]; at the dipole stage there is no magnitude so the mask is used. The
  best `alpha1`/`lambda` come from the parameter sweep, not hard-coded here.
- **`tol_update`/`iterations` defaults** (1.0 / 50) are the `nlL1TV.m` defaults — L1-QSM converges
  more slowly than L2; the human may want more iterations. Verify on the phantom.
- **GPU disabled** — scoring Runtime is CPU-only.
- **License:** FANSI ships no LICENSE file (README: "academic and research", BSD-style disclaimer) →
  `license: academic use; cite paper`.
