# Building medi-cornell (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler** and bake it onto the R2023b
MATLAB Runtime. R2023b because it is the licensed MATLAB the fidelity check runs on
([`../../fidelity/matlab/`](../../fidelity/matlab/README.md)), so the container and the reference
runs share one release. Bundled NIfTI toolbox and OS gzip (no JVM), plus the Cornell **MEDI toolbox
2024.11.26**, the release QSM.rs's MEDI port follows.

Stage: `dipole` — consumes `localfield` (ppm), `magnitude` (the echoes), `mask`, `params`; `MEDI_L1`
dipole inversion on the provided local field → `chimap` (ppm).

## 1. Fetch build-time deps (not committed)
```bash
cp -r /path/to/NIfTI_20140122                        algorithms/medi-cornell/nifti   # Jimmy Shen toolbox
cp -r /path/to/MEDI_toolbox-2024.11.26/functions     algorithms/medi-cornell/medi    # Cornell MEDI toolbox
# store_CG_results is only referenced by an unused MEDI_L1 debug branch — add a no-op stub so mcc resolves it:
printf 'function store_CG_results(varargin)\nend\n' > algorithms/medi-cornell/medi/store_CG_results.m
```
[`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`) is the same recipe as a script.

## 2. Compile
```bash
cd algorithms/medi-cornell
matlab -batch "addpath('nifti'); addpath('medi'); mcc('-m','recon.m','-o','recon','-d','.')"   # -> ./recon
```
mcc traces only the MEDI functions `recon.m` actually calls (MEDI_L1 and its dependencies; there is
no pcode); the DICOM/bet2/GUI files in `medi/` are ignored. Check that `unresolvedSymbols.txt` and
`mccExcludedFiles.log` list nothing. The harness does this compile as a Slurm job
(`fidelity/matlab/submit.sh medi-cornell build`; log in `reports/build.txt`).

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/matlab-medi:v4 .   # needs ./recon from §2
podman push  ghcr.io/astewartau/qsm-ci/matlab-medi:v4
```
Keep the package public, pin `image:` in `algorithm.yml` by the pushed digest, and rerun the
fidelity check ([`fidelity/REPORT.md`](fidelity/REPORT.md)). The [`Dockerfile`](Dockerfile) is the
R2023b Runtime base (pinned by digest) plus `recon`.

Images: `v1`, `v2` (R2026a Runtime; see `fidelity/REPORT.md` for which MEDI release `v2` holds);
`v3` (R2023b, MEDI 2024.11.26, Cornell's default `lambda` 1000, SMV and MERIT off); `v4` (as `v3`,
with every default MEDI_L1's own; see `fidelity:` in `algorithm.yml`). Never overwrite a tag.

## Defaults: MEDI 2024.11.26's own
Every parameter defaults to what `MEDI_L1` (`parse_QSM_input.m`) does when the option isn't passed.
That is also what the toolbox's pipeline script (`README.m`) runs on `RDF.mat`:
`MEDI_L1('lambda',1000,'lambda_CSF',100,'merit','smv',5)`.

| Parameter | Default | `MEDI_L1` option |
|---|---|---|
| `lambda` | 1000 | `'lambda'` |
| `smv`, `smv_radius` | 1, 5 mm | `'smv', 5` (0: `'nosmv'`) |
| `smv_shrink_mask` | 1 | `'smv_shrink_mask'` |
| `merit` | 1 | `'merit'` (0: `'nomerit'`) |
| `csf`, `lambda_csf` | 1, 100 | `Mask_CSF` in `RDF.mat`, `'lambda_CSF'` |
| `csf_r2s_threshold`, `csf_erode` | 5 Hz, 1 | `extract_CSF`'s `thresh_R2s`, `flag_erode` |
| `percentage` | 0.9 | `'percentage'` |
| `data_weighting` | 1 | `'data_weighting'` |
| `max_iter`, `tol_norm_ratio` | 10, 0.1 | `'max_iter'`, `'tol_norm_ratio'` |
| `cg_max_iter`, `cg_tol` | 100, 0.01 | `'cg_max_iter'`, `'cg_tol'` |
| `zeropad` | 0 | `'zeropad'` (done by `recon.m`; see below) |

The parameters match QSM.rs's `MediParams` (`src/inversion/medi.rs`), so a parity pair can set both
sides alike. `MEDI_L1` reads everything else from `RDF.mat`, which `recon.m` fills as `README.m` does
from QSM-CI's inputs:

- **`iMag`** `= sqrt(sum(mag.^2, 4))` over the echo magnitudes, as `README.m`.
- **`N_std`** from `Fit_ppm_complex` on the echo magnitudes. `README.m` takes it from
  `Fit_ppm_complex(iField)` on the complex echoes; its noise estimate (`dp1`) depends only on their
  magnitudes, so it is the same `N_std`.
- **`Mask_CSF`** (MEDI+0) `= extract_CSF(arlo(TE, mag), Mask, voxel_size)`, as `README.m`, on
  QSM-CI's mask. With fewer than three echoes `recon.m` leaves it out and `MEDI_L1` runs without the
  CSF term: `arlo` gives no R2* for one echo and 0 everywhere for two, which would make the whole
  central sphere "CSF". It is also left out when `extract_CSF` errors (fewer than three low-R2*
  regions in the central sphere) or finds no voxels (`MEDI_L1` would return NaN).
- **`RDF`** is the local field from QSM-CI's `bfr` stage, where `README.m` runs PDF.
- **`CF`, `delta_TE`**: see Units.

Three choices are `recon.m`'s, all as QSM.rs makes them:

- **Odd axes with SMV.** `sphere_kernel.m` builds its grid as `-N/2:N/2-1`, which along an odd axis
  centres the sphere half a voxel off the grid, and `MEDI_L1` diverges there. With SMV on, `recon.m`
  adds one voxel to each axis still odd after `zeropad` and crops the result back. Even grids are
  untouched.
- **Padding.** `recon.m` does the padding (`zeropad` and the odd axes) itself, as `MEDI_L1`'s
  `'zeropad'` means to: zeros appended at the end of each axis of what `MEDI_L1` reads from
  `RDF.mat`, and the result cropped back. In 2024.11.26 `'zeropad'` itself errors, because
  `parse_QSM_input` pads the volumes but leaves `opts.matrix_size` (`reg_MEDI`'s epsilon) and
  `opts.Mask`/`Mask_CSF` (`reg_CSF`) at the unpadded size. The CSF mask is found on the input grid
  and then padded.
- **Outside the mask.** `MEDI_L1` zeroes χ outside the mask it inverted on (with SMV, the eroded
  mask) and then subtracts the CSF mean from every voxel. `recon.m` sets χ back to 0 outside that
  mask (from `MEDI_L1`'s results file), as the other inversions leave it; inside, χ is `MEDI_L1`'s.

## Units
`localfield` is ppm; MEDI works in radians. As in `README.m`, `CF` is the centre frequency
(42.576 MHz/T · `B0`) and `delta_TE` the echo spacing `TE(2) − TE(1)`, or `TE` for one echo
(`Read_DICOM`). `recon.m` converts `iFreq = field·1e-6·2π·CF·delta_TE` and `MEDI_L1` converts back
via `/(2π·delta_TE·CF)·1e6`, so χ is ppm. The data term is nonlinear, so χ depends on this scale;
`v3` and earlier used a fixed 3 T, 8 ms scale instead.
