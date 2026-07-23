# HD-QSM — Hybrid Data-fidelity QSM (MATLAB)

**STATUS: scaffold — needs image build (MATLAB Compiler license required).** Source is complete;
the compiled `recon` binary and pushed image are the human's job (see `BUILD.md`).

## What it does
Hybrid Data-fidelity QSM (Lambert et al., *MRM* 2022, doi:10.1002/mrm.29218). A **two-stage linear**
dipole inversion: an L1 data-fidelity stage produces a discrepancy map that re-weights a second L2
stage, combining L1 robustness to phase inconsistencies with L2 smoothness. Code: `HDQSM.m` from
`github.com/mglambert/HD-QSM`, which builds on the FANSI toolbox.

- **Stage:** `dipole` — consumes `localfield` (ppm), `mask`, `params`; produces `chimap` (ppm).

## Units handling
HD-QSM is a **linear** inversion (`real(ifftn(kernel.*Fx))`, no `sin`/`exp`), hence scale-linear:
output susceptibility is in the same units as the input field. `recon.m` feeds the **ppm** local
field directly and writes a **ppm** chimap — **no radian conversion** (this is the key difference
from the FANSI *nonlinear* methods fansi/ndi/l1-qsm/wh-qsm). `alphaL2` is calibrated to the ppm
(B0-normalized) field scale, matching the toolbox example.

## Parameters (defaults from the HDQSM.m example)
| name | default | meaning |
|------|---------|---------|
| `alphaL2` | 1.64e-5 (10^-4.785) | L2-stage TV regularization weight |
| `mu1L2` | 1.64e-4 | L2-stage gradient-consistency ADMM weight (= 10·alphaL2) |
| `iterationsL1` | 20 | L1 (discrepancy-estimation) stage iterations |
| `iterationsL2` | 80 | L2 (final) stage iterations |
| `tol_update` | 1.0 | L2-stage convergence threshold (percent update) |

(L1-stage `alphaL1`/`mu1L1` default *inside* HDQSM.m to `sqrt(alphaL2)` / `sqrt(mu1L2)`.)

## Assumptions the human must verify
- **Repo name is `mglambert/HD-QSM`** (hyphen). The task/memo referenced `mglambert/HDQSM`, which
  returns 404 — corrected here and in `BUILD.md`.
- **License is MIT** — HD-QSM ships an MIT LICENSE file (contrary to the task's assumption that the
  repo had none). Recorded as `license: MIT`.
- **Own image** `ghcr.io/astewartau/qsm-ci/hd-qsm:v1` (NOT shared with the FANSI family), though it
  still needs FANSI at *compile* time (`gradient_calc`, dipole kernel).
- **`alphaL2` default (10^-4.785)** is the value hard-coded in the HDQSM.m example, calibrated to a
  ppm-normalized brain. The QSM-CI phantom differs; the real best value comes from the parameter
  sweep (no `tuned:` hard-coded here). Verify it converges/behaves on the phantom.
- **Kernel choice.** `recon.m` uses FANSI's continuous angulated kernel `dipole_kernel_angulated`.
  The HDQSM example passes a `kernel` the caller builds; the toolbox does not fix which. Confirm the
  continuous kernel matches the paper's intent (the discrete kernel `dipole_kernel_fansi(...,1)` is
  an alternative).
- **Weighting:** binary mask (no magnitude at the dipole stage).
- **DOI 10.1002/mrm.29218** confirmed via Crossref.
