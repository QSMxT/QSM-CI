# WH-QSM — Weak-Harmonic QSM (MATLAB)

**STATUS: scaffold — needs image build (MATLAB Compiler license required).** Source is complete;
the compiled `recon` binary and pushed image are the human's job (see `BUILD.md`).

## What it does
Weak-Harmonic QSM (Milovic et al., *MRM* 2019, doi:10.1002/mrm.27483). A dipole inversion that
**jointly** estimates the susceptibility map and a residual *harmonic* (background) field that
survived background-field removal — correcting imperfect BFR during the inversion. TV regularized;
implementation is `WH_nlTV.m` from Carlos Milovic's **FANSI toolbox**.

## Stage — `dipole` (justification)
WH-QSM consumes the **local field**, not the total field. Its purpose is to mop up *remnant*
background field in an already-BFR'd local field map, jointly with inversion. The `WH_nlTV.m` header
states it "remove[s] background field remnants from *local* field maps and calculate[s] the
susceptibility of tissues simultaneously." It is therefore a `dipole`-stage method (consumes
`localfield`, produces `chimap`), **not** a `bfr+dipole` span (which would consume the *total*
field). Chosen accordingly per `CONTRACT.md`.

## Units handling
`WH_nlTV.m` uses a `sin(z - phase)` data term → input in **radians**. `recon.m` converts
`phase_rad = field * 2*pi * 42.58 * B0 * TE`, runs `WH_nlTV`, then divides the susceptibility output
by the same `phs_scale` to return **ppm**. (WH_nlTV also returns `out.phi`, the harmonic field — not
used here; only `chimap` is a QSM-CI artifact.)

## Parameters
| name | default | meaning |
|------|---------|---------|
| `alpha1` | 3e-4 | gradient L1 (TV) penalty |
| `beta` | 150 | weak-harmonic constraint weight (WH_nlTV default) |
| `mu1` | 3e-2 | gradient-consistency ADMM weight (= 100·alpha1) |
| `iterations` | 300 | max ADMM outer iterations |
| `tol_update` | 0.1 | convergence threshold (percent update) |

## Assumptions the human must verify
- **Stage = `dipole`** (see justification above). If the intent was to test WH-QSM as a
  background-remnant remover fed the *total* field, that would instead be a `bfr+dipole` span with a
  different recon; this scaffold implements the local-field (dipole) interpretation, which matches
  the reference docstring.
- **Image is SHARED** with `fansi`, `ndi`, `l1-qsm`: `ghcr.io/astewartau/qsm-ci/fansi:v1`
  (see `BUILD.md`).
- **`iterations=300`.** The `WH_nlTV.m` header warns the harmonic field needs *hundreds* of
  iterations to converge (the plain default of 150 is "for testing"). 300 is a compromise; the human
  should confirm convergence and watch the 2 h time limit on the full-size phantom.
- **`beta=150`** is the WH_nlTV default; the best value comes from the parameter sweep.
- **Weighting:** binary mask (no magnitude at the dipole stage); `params.mask` set for the ROI.
- **GPU disabled** — scoring Runtime is CPU-only.
- **DOI 10.1002/mrm.27483** — "Weak-harmonic regularization for QSM", Milovic et al. Confirmed via
  Crossref (the task text said "MRM 2019").
- **License:** FANSI ships no LICENSE file (README: "academic and research", BSD-style disclaimer) →
  `license: academic use; cite paper`.
