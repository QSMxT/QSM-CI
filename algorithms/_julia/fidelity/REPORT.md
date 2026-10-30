# Julia-original fidelity report

QSMxT/QSM-CI#299: do the Julia submissions run the authors' packages reproducibly, in a pinned
environment? To rerun the check, see [`README.md`](README.md).

- **Checked:** 2026-10-28 on the QSM-CI workstation: Intel Core i5-11500 (rocketlake, AVX-512),
  12 logical CPUs, podman.
- **Image:** `ghcr.io/astewartau/qsm-ci/julia-qsm@sha256:b3c048acd8a88f23b7a04378f2b85dbac433bcc78b3d9cdf8ce58eb8a7478185` (`v1`), Julia 1.10.11 and the
  committed [`../env/Manifest.toml`](../env/Manifest.toml): QSM.jl fde4b92 (0.5.4), ROMEO.jl 08776d4
  (1.6.0), MriResearchTools.jl 771eadf (3.8.0), QuantitativeSusceptibilityMappingTGV.jl 6c0886a
  (0.5.2), CLEARSWI.jl 0949bc5 (1.7.0), FFTW.jl 1.8.1, NIfTI.jl 0.6.3.
- **Host comparison:** the official Julia 1.10.11 binary for Linux x86-64, with the same Manifest
  instantiated in a fresh depot, running each submission's `run.sh` (`qsm-ci run --runner local`)
  without the image's sysimage, so every package was compiled natively on the host.
- **Threads:** 4 Julia threads, FFTW 4, BLAS 1 in every run (`run.sh`, `qsmci_io.jl`).
- **Case:** `invivo`, the public travelling-head acquisition `prisma-bridge-run1` (Siemens Prisma,
  2.89 T, 5 echoes, 1 mm, 184×256×128) with its mask. The field-mapping methods read its phase
  and magnitude; the bfr methods and TGV read the total field from `romeo-qsmrs`; the dipole
  methods read the local field `vsharp-qsmrs` made from that total field. Every method gets the
  same inputs as its QSM.rs pair.

## Result: identical

**Every submission's output is bit-identical across two runs of the image, and between the
image and the host Julia.** No voxel differs.

| method | image twice | image vs host Julia | run time, s (image, image, host) |
|---|---|---|---|
| `ismv-qsmjl` | identical | identical | 4.5 / 4.8 / 9.6 |
| `laplacian-qsmjl` | identical | identical | 6.7 / 9.5 / 24.5 |
| `nltv-qsmjl` | identical | identical | 26.5 / 25.4 / 30.0 |
| `romeo-romeojl` | identical | identical | 11.3 / 11.4 / 33.8 |
| `rts-qsmjl` | identical | identical | 5.7 / 5.3 / 11.5 |
| `sharp-qsmjl` | identical | identical | 3.5 / 3.6 / 9.4 |
| `tgv-tgvjl` | identical | identical | 484.0 / 556.4 / 489.2 |
| `tikhonov-qsmjl` | identical | identical | 3.8 / 3.7 / 7.1 |
| `tkd-qsmjl` | identical | identical | 3.7 / 3.8 / 7.0 |
| `tsvd-qsmjl` | identical | identical | 3.8 / 3.8 / 7.1 |
| `tv-qsmjl` | identical | identical | 12.7 / 12.8 / 18.0 |
| `vsharp-qsmjl` | identical | identical | 4.4 / 4.4 / 9.6 |

The image's run times include starting the container; the host's include compiling every
package on first use, which the sysimage saves the image. `tgv-tgvjl` runs the package's default
iteration count (1655 at 1 mm, step size 3) on four threads.

**Scope.** Identical output holds on this CPU at this thread count. FFTW and the SIMD packages
under QSM.jl pick kernels by CPU features, so another CPU may round differently; the
`julia-originals` workflow repeats the image-twice check on GitHub's hosted runners, on the
in-silico phantom, for every pull request that changes these submissions.

## First look against the QSM.rs ports

Not a gate. Each original against its `-qsmrs` pair (QSMxT v10.0.0, QSM.rs v0.39.0) on the same
`invivo` inputs, inside the mask where both outputs are non-zero (the bfr methods and TGV erode
the mask, each its own way). NRMSE is `100·‖jl − rs‖ / ‖rs‖`. *Defaults* are the original's own;
*matched* adds the `--set` values from each submission's README (for TGV, QSM.rs's ppm α
converted to the package's rad units at TE1 and B0).

| method | port | settings | NRMSE vs port, % | correlation | max abs diff in mask | voxels |
|---|---|---|---|---|---|---|
| `ismv-qsmjl` | `ismv-qsmrs` | defaults | 50 | 0.8890 | 0.206 | 1343142 |
| `ismv-qsmjl` | `ismv-qsmrs` | `radius=5` `tol=1e-6` `max_iter=50` | 3.05e-09 | 1.0000 | 4.66e-10 | 1343142 |
| `laplacian-qsmjl` | `laplacian-qsmrs` | defaults | 46.1 | 0.9405 | 0.762 | 1699930 |
| `laplacian-qsmjl` | `laplacian-qsmrs` | `mask_phase=true` `demean=true` | 1.39e-09 | 1.0000 | 1.86e-09 | 1699930 |
| `nltv-qsmjl` | `nltv-qsmrs` | defaults | 84.8 | 0.5580 | 1.45 | 1699930 |
| `nltv-qsmjl` | `nltv-qsmrs` | `pad=-1` | 85.1 | 0.5508 | 1.46 | 1699930 |
| `romeo-romeojl` | `romeo-qsmrs` | defaults | 25.3 | 0.9670 | 4 | 1699930 |
| `romeo-romeojl` | `romeo-qsmrs` | `weights=romeo4` `individual_unwrapping=true` `correct_global=true` `temporal_uncertain_unwrapping=0.5` `phase_offset_sigma_mm=4` | 6.41 | 0.9976 | 1.21 | 1699930 |
| `rts-qsmjl` | `rts-qsmrs` | defaults | 30.3 | 0.9537 | 0.53 | 1699930 |
| `rts-qsmjl` | `rts-qsmrs` | `pad=-1` | 30.3 | 0.9536 | 0.53 | 1699930 |
| `sharp-qsmjl` | `sharp-qsmrs` | defaults | 68.4 | 0.8678 | 0.0217 | 627587 |
| `sharp-qsmjl` | `sharp-qsmrs` | `radius=6` | 12.6 | 0.9922 | 0.00776 | 1275505 |
| `tgv-tgvjl` | `tgv-qsmrs` | defaults | 66.1 | 0.7515 | 1.88 | 1443191 |
| `tgv-tgvjl` | `tgv-qsmrs` | `iterations=1000` `laplacian=romeo` `alpha1=0.000258446` `alpha0=0.000775339` | 43.7 | 0.9002 | 1.68 | 1443191 |
| `tikhonov-qsmjl` | `tikhonov-qsmrs` | defaults | 1.88 | 0.9998 | 0.0052 | 1699930 |
| `tikhonov-qsmjl` | `tikhonov-qsmrs` | `pad=-1` | 0 | 1.0000 | 0 | 1699930 |
| `tkd-qsmjl` | `tkd-qsmrs` | defaults | 7.49 | 0.9972 | 0.0347 | 1699930 |
| `tkd-qsmjl` | `tkd-qsmrs` | `pad=-1` | 0 | 1.0000 | 0 | 1699930 |
| `tsvd-qsmjl` | `tsvd-qsmrs` | defaults | 15.6 | 0.9878 | 0.0506 | 1699930 |
| `tsvd-qsmjl` | `tsvd-qsmrs` | `pad=-1` | 4.65e-12 | 1.0000 | 3.64e-12 | 1699930 |
| `tv-qsmjl` | `tv-qsmrs` | defaults | 50.5 | 0.8854 | 0.854 | 1699930 |
| `tv-qsmjl` | `tv-qsmrs` | `lambda=2e-4` `pad=-1` | 0.738 | 1.0000 | 0.07 | 1699930 |
| `vsharp-qsmjl` | `vsharp-qsmrs` | defaults | 39.1 | 0.9295 | 0.299 | 1563968 |
| `vsharp-qsmjl` | `vsharp-qsmrs` | `max_radius=12` `min_radius=1` `radius_step=1` | 15.5 | 0.9881 | 0.0418 | 1633252 |

- **Same result once matched:** TKD, TSVD and Tikhonov (identical, or to 4e-12 ppm, with QSM.jl's
  fast-FFT padding off), iSMV and Laplacian field mapping (to float32 rounding), TV (0.74 %).
  So the dipole kernel, units and conventions agree.
- **Different algorithm:** NLTV. QSM.rs v0.39.0's `nltv` is an iteratively reweighted TV, not
  QSM.jl's nonlinear-data-term method (Milovic et al. 2018); no setting makes them the same.
- **Still different when matched, worth a look on the QSM.rs side:** RTS (30 %; QSM.rs v0.39.0
  calls itself a port of QSM.jl's `rts` with its defaults, and padding is not the cause), TGV
  (44 %; QSM.rs stops early at tol 1e-5 and solves in ppm), SHARP (12.6 %), V-SHARP (15.5 %),
  ROMEO (6.4 %, max 1.2 ppm, where the seed choice and MCPC-3D-S masks differ).
