# FANSI — Fast Nonlinear Susceptibility Inversion (MATLAB)

**STATUS: scaffold — needs image build (MATLAB Compiler license required).** The source
(`recon.m`, `run.sh`, `algorithm.yml`, `Dockerfile`) is complete; the compiled `recon` binary and
the pushed image are the human's job (see `BUILD.md`).

## What it does
Nonlinear total-variation regularized dipole inversion from Carlos Milovic's **FANSI toolbox**
(Milovic et al., *MRM* 2018, doi:10.1002/mrm.27073). Solves the QSM dipole-inversion problem with a
nonlinear (complex-exponential) data-fidelity term and TV (or TGV) regularization via ADMM.

- **Stage:** `dipole` — consumes `localfield` (ppm), `mask`, `params`; produces `chimap` (ppm).
- **Solver:** `nlTV` by default; set `isTGV=1` to use `nlTGV` (total generalized variation).

## Units handling
FANSI's *nonlinear* solvers contain a `sin(phi - phase)` data term and therefore require the input
field in **radians**, not ppm. `recon.m`:
1. converts the ppm local field to radians: `phase_rad = field * 2*pi * 42.58 * B0 * TE`
   (42.58 MHz/T absorbs the ppm 1e6 factor),
2. runs `nlTV`/`nlTGV`,
3. divides the output by the same `phs_scale` to return **ppm**.
This exactly mirrors the toolbox's own `script_qsmchallenge.m`.

## Parameters (defaults match FANSI recommendations)
| name | default | meaning |
|------|---------|---------|
| `alpha1` | 3e-4 | gradient L1 (TV) penalty |
| `mu1` | 3e-2 | gradient-consistency ADMM weight (= 100·alpha1) |
| `iterations` | 150 | max ADMM outer iterations |
| `tol_update` | 0.1 | convergence threshold (percent update) |
| `isTGV` | 0 | 0 = TV (nlTV), 1 = TGV (nlTGV) |

## Assumptions the human must verify
- **Image is SHARED** with `ndi`, `l1-qsm`, `wh-qsm` (all FANSI): `ghcr.io/astewartau/qsm-ci/fansi:v1`.
  See `BUILD.md` for how to lay out the shared/multi-binary image.
- **`alpha1` default (3e-4)** is a literature-typical value from the FANSI challenge script, tuned
  there for a ppm-normalized brain at ~3 T. The QSM-CI phantom differs; the *real* best value comes
  from the parameter sweep (do not hard-code a `tuned:` here). Verify it converges on the phantom.
- **Weighting:** the dipole stage provides no magnitude, so the data-fidelity weight is the binary
  mask. FANSI normally uses magnitude; mask weighting is the reasonable stage-appropriate choice.
- **GPU disabled** (`isGPU=false`) — the scoring MATLAB Runtime is CPU-only.
- **License:** FANSI ships no LICENSE file; README grants "academic and research" use with a
  BSD-style disclaimer. Recorded as `license: academic use; cite paper`.
