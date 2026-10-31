# Building tfi-cornell (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler** and bake it onto the R2023b
MATLAB Runtime, as `../medi-cornell/BUILD.md`. The method is TFI (Liu et al., MRM 2017) as the
Cornell **MEDI toolbox 2024.11.26** implements it: `MEDI_L1.m` with a preconditioner `P` in
`RDF.mat`. QSM.rs's TFI port (`src/inversion/tfi.rs`) follows the same code.

Stage: `bfr+dipole`. It consumes `totalfield` (ppm), `magnitude` (the echoes), `mask` and `params`
and writes `chimap` (ppm), 0 outside the mask.

## 1. Fetch build-time deps (not committed)
```bash
cd algorithms/tfi-cornell
cp -r /path/to/NIfTI_20140122 nifti
cp -r /path/to/MEDI_toolbox-2024.11.26/functions medi
# store_CG_results is only referenced by an unused MEDI_L1 debug branch: a no-op stub lets mcc resolve it.
printf 'function store_CG_results(varargin)\nend\n' > medi/store_CG_results.m
```
[`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`) is the same recipe as a script.

## 2. Compile
```bash
matlab -batch "addpath('nifti'); addpath('medi'); mcc('-m','recon.m','-o','recon','-d','.')"
```
mcc traces only the MEDI functions `recon.m` reaches. Check that `unresolvedSymbols.txt` and
`mccExcludedFiles.log` list nothing (`submit.sh tfi-cornell build`).

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/matlab-medi:tfi-v1 .
podman push  ghcr.io/astewartau/qsm-ci/matlab-medi:tfi-v1
```
The image is a tag of the public `matlab-medi` package. Pin `image:` by the pushed digest and rerun
the fidelity check. Never overwrite a tag.

## Settings
Cornell's own TFI script (`TFI_L1.m`) is not public. What the toolbox settles comes from
`MEDI_L1`'s defaults (`parse_QSM_input.m`); what it does not, from the paper, as QSM.rs records:

| Parameter | Default | From |
|---|---|---|
| `precond` | 30 | eq. 3: `P = 1` in the mask, `P_B` outside; 30 is the paper's in-vivo value |
| `linear` | 1 | eq. 5, `MEDI_L1`'s `'linear'` option. With the exponential default, `MEDI_L1` fails on in-vivo total fields (the field wraps inside `exp(i·)`) |
| SMV | off | the total field is inverted whole; an SMV high-pass would remove the background TFI fits (`'nosmv'`) |
| `lambda` | 1000 | `MEDI_L1` |
| `merit` | 1 | `MEDI_L1` |
| `percentage`, `data_weighting` | 0.9, 1 | `MEDI_L1` |
| `max_iter`, `tol_norm_ratio` | 10, 0.1 | `MEDI_L1` |
| `cg_max_iter`, `cg_tol` | 100, 0.01 | `MEDI_L1` |

These match QSM.rs's `TfiParams` defaults. Not used: the R2*-based preconditioner (eq. 4), zero
padding and the CSF zero reference, as in QSM.rs.

`RDF.mat` is filled as `README.m` does from QSM-CI's inputs: `RDF` (and `iFreq`) the total field in
radians over the echo spacing (`field·1e-6·2π·CF·delta_TE`, `CF` = 42.576 MHz/T · `B0`,
`delta_TE` = `TE(2) − TE(1)`); `iMag` the root sum of squares of the echo magnitudes; `N_std` from
`Fit_ppm_complex` on the magnitudes; `Mask` QSM-CI's mask; `P` as above. `MEDI_L1` returns
`P·y` in ppm, masked by `Mask`.
