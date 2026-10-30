# C++ and Python originals: fidelity and first look

QSMxT/QSM-CI#302, part of #295. The originals of QSM.rs's ports that are written in C++ or Python,
each in a pinned image:

| original | version | image | QSM.rs port | how it runs here |
|---|---|---|---|---|
| ANTs `N4BiasFieldCorrection` | 2.4.3 (ITK 5.3.0), official release binary | `ants-n4` ([`algorithms/_ants`](../../algorithms/_ants)) | `utils/n4.rs` | fixture run |
| scikit-image `unwrap_phase` (3-D best path) | 0.26.0 | `py-originals` ([`algorithms/_python-originals`](../../algorithms/_python-originals)) | `unwrap/bestpath.rs` | fixture run |
| DIPY `gibbs_removal` | 1.12.1 | `py-originals` | `utils/gibbs.rs` | fixture run |
| DIPY `mppca` | 1.12.1 | `py-originals` | `utils/denoise.rs` | fixture run |
| FSL `bet2` | Bostrix/FSL-BET2 d5acd7f | **local only** ([`algorithms/_bet2`](../../algorithms/_bet2)) | `bet/` | fixture run |
| WaveSep | ZhenghanFang/WaveSep f3a192e | `wavesep` v1 ([`algorithms/wavesep`](../../algorithms/wavesep)) | `separation/wavesep.rs` | QSM-CI stage: `wavesep` / `wavesep-qsmrs` |

## Why fixture runs

N4, Gibbs removal, MP-PCA and best-path unwrapping are not QSM-CI stages: they produce no artifact
the contract defines (a corrected or denoised magnitude, a single unwrapped echo), and the parity
workflow compares a stage's produced artifact (`scripts/parity.py`). Rather than add stages and
artifacts that only these pairs would use, each original runs as a *fixture run*: its pinned image,
a thin call script mounted at `/algo` (code mounted, not baked, as for every submission), fixed
inputs cut from a public case, nothing scored. That keeps them out of scoring, the site and the
contract by construction, so they need no `parity_only` flag.

These are the originals QSM.rs's fixture tests (astewartau/QSM.rs#317) should be generated from:
the outputs are bit-reproducible (below), small cases cost seconds, and a QSM.rs test that checks
its port against them runs on every QSM.rs change, which is a tighter loop than the release gate.

BET would be a `brain-extraction` stage entry, but its image cannot be published (see
[`algorithms/_bet2/README.md`](../../algorithms/_bet2/README.md)), and an entry whose image CI cannot
pull would break the PR smoke gate; so it is a fixture run too, local only.

WaveSep is already a QSM-CI `chi-separation` entry (`wavesep`, scored); its port is the new
`wavesep-qsmrs` entry, and the two share `algorithm: wavesep`, so the parity workflow can run them as
a pair.

## Fidelity: what is checked

1. **Pinned.** Base images by digest; ANTs by the release zip's SHA-256; Python wheels by hash
   (`requirements.lock`, installed `--require-hashes --no-deps`); bet2 and WaveSep source by commit.
2. **Deterministic.** Each image run twice on the same inputs gives bit-identical output, at a fixed
   thread count: ITK 4 threads for N4 (its B-spline fit sums in per-thread blocks, so the count
   matters), OpenMP/OpenBLAS/MKL 1 for the Python originals, bet2 single-threaded.
3. **Same outside the container.** The same call scripts on the host: the same ANTs release binary
   (on Arch's glibc/libstdc++/libm instead of Ubuntu 22.04's), and a standalone CPython 3.12.16
   (python-build-standalone) with the same `requirements.lock`. bet2: this workstation has no CMake,
   so the check is instead a second build of the same commit with another toolchain (Debian 12,
   GCC 12, instead of Ubuntu 22.04, GCC 11). WaveSep: a rebuild from the committed Dockerfile on a
   current Python 3.10.20 base, against the published v1 image.

## Running it

```bash
# A QSM-CI input dir (phase, magnitude, mask .nii.gz) → the fixture inputs.
python fidelity/cpp-py/harness.py prepare --case path/to/case --out fx
python fidelity/cpp-py/harness.py determinism --case fx --out out          # every original, twice
python fidelity/cpp-py/harness.py host --case fx --out out \
    --python /path/to/py312/bin/python --n4-bin /path/to/ants-2.4.3/bin/N4BiasFieldCorrection
# First look against QSM.rs: build the probe at the QSM.rs commit in its Cargo.toml.
cargo build --release --manifest-path fidelity/cpp-py/qsmrs-probe/Cargo.toml
python fidelity/cpp-py/harness.py pair --case fx --out out \
    --probe fidelity/cpp-py/qsmrs-probe/target/release/qsmrs-probe [--qsmxt-image <qsmxt image>]
```

`--ops` picks originals (`n4,bestpath,gibbs,mppca,bet-f0.2,bet-f0.5`). The BET ops need the local
image (`podman build -t localhost/qsm-ci/bet2:d5acd7f algorithms/_bet2`). `qsmrs-probe` calls
QSM.rs's ports directly, for the ones qsmxt has no command for (best path, Gibbs, MP-PCA) and for
BET's subdivisions, which `qsmxt mask bet` does not take; N4 also runs through `qsmxt homogeneity
--method n4` when a qsmxt image is given.

The raw numbers are in [`results/`](results).

## Results (2026-10-28)

- **Where:** the QSM-CI workstation, Intel Core i5-11500 (12 logical CPUs), podman.
- **Case (all but WaveSep):** the public travelling-head acquisition `prisma-bridge-run1` (Siemens
  Prisma, 2.89 T, 5 echoes, 1 mm, 184×256×128) with its mask (1,699,930 voxels).
- **Case (WaveSep):** the χ-separation phantoms are token-gated and not on the workstation, so a
  synthetic case: the in-silico phantom's χ_total (164×205×205, 1 mm), the mask its non-zero region
  eroded by 3 voxels, and R2′ = 137·(χ+ − χ−) for a smooth synthetic split of χ_total.

| image | digest |
|---|---|
| `ghcr.io/astewartau/qsm-ci/ants-n4:v1` | `sha256:621644e172c4872f1d181c9c18dc8717c40aece19de8d28c31fce93028017c49` |
| `ghcr.io/astewartau/qsm-ci/py-originals:v1` | `sha256:7654140b9e7ff00552590d945db9b8d52c526fd01b8e36d5e1ad524b02b510ed` |
| `localhost/qsm-ci/bet2:d5acd7f` | local only, not published |
| `ghcr.io/astewartau/qsm-ci/wavesep:v1` | `sha256:c96094a98049ccfb9d660a2463ef772502b30dcb412095e45641d67edeb8791a` (unchanged) |

### Fidelity: every original is reproducible

| original | image twice | outside the container | run time (image) |
|---|---|---|---|
| N4 (ANTs 2.4.3, 4 ITK threads): corrected image and bias field | identical | identical (same binary on the host) | 13 s |
| best path (scikit-image 0.26.0, `rng=0`) | identical | identical (host CPython 3.12.16, same lock) | 2 s |
| Gibbs (DIPY 1.12.1, 1 process), 5 echoes | identical | identical (host) | 180 s |
| MP-PCA (DIPY 1.12.1, 1 thread), 5 echoes | identical | identical (host) | 230–250 s |
| bet2 `-f 0.2` and `-f 0.5` | identical | identical (second build: Debian 12, GCC 12) | 1.4 s |
| WaveSep v1 | identical | identical (rebuild from the committed Dockerfile; also identical at 1 BLAS thread and at the default) | 75–90 s |

**WaveSep runs the original unmodified.** The image's `/opt/wavesep/wavesep` is byte-identical to
ZhenghanFang/WaveSep f3a192e (the latest commit) apart from `__pycache__`. `recon.py` differs from
the authors' driver (`wavesep/utils/run_wavesep_qsm.py`) in three ways, none in the solver: it
zero-pads each axis to a multiple of 2^L so PyWavelets' periodization round-trips (QSM.rs pads the
same way); it attaches a no-op evaluator, because the authors' `solve()` prints `metrics[-1]`,
which fails without ground truth; and it writes χ− as a positive magnitude, as the contract wants.

### First look against QSM.rs main (not a gate)

QSM.rs main da928e0 (what QSMxT main 8a7072a pins), built with `parallel` as qsmxt builds it:
`qsmrs-probe`, and for N4 and WaveSep also the qsmxt binary built from QSMxT main. Inside the mask.

| original | port | output | NRMSE % | r | max \|Δ\| | p99 \|Δ\| | max \|Δ\| / max \|ref\| |
|---|---|---|---|---|---|---|---|
| N4 | `n4_bias_correction` | corrected | 3.09 | 0.99935 | 57.2 | 27.5 | 2.8 % |
| N4 | `n4_bias_correction` | bias field | 3.16 | 0.99198 | 0.041 | 0.029 | 5.4 % |
| N4 | `qsmxt homogeneity --method n4` | corrected | 3.09 | 0.99935 | 57.3 | 27.5 | 2.8 % |
| N4, same voxels, axis-aligned header | `n4_bias_correction` | corrected | 0.0020 | 1.0000 | | | 4.4e-5 |
| best path | `unwrap_bestpath` | unwrapped | 1.1e-6 | 1.0000 | 9.1e-7 rad | 6.4e-8 rad | 4.3e-8 |
| Gibbs | `gibbs_unring` (3-D) | 5 echoes | 2.04 | 0.99747 | 322 | 18.8 | 16 % |
| MP-PCA | `mppca_denoise`, radius 2 | 5 echoes | 0.97 | 0.99947 | 142 | 9.7 | 5.5 % |
| WaveSep | `qsmxt separate wavesep` (v10.0.0 and main alike) | χ+ | 0.114 | 0.9999988 | 0.066 ppm | 0.024 ppm | |
| WaveSep | ″ | χ− | 1.08 | 0.99993 | 0.063 ppm | 0.023 ppm | |

| original | port | settings | Dice | voxels (original / port) |
|---|---|---|---|---|
| bet2 `-f 0.2` | `run_bet` | subdivisions 4 (default) | 0.9915 | 1,798,293 / 1,809,956 |
| bet2 `-f 0.2` | `run_bet` | subdivisions 5 | 0.9912 | 1,798,293 / 1,816,355 |
| bet2 `-f 0.5` | `run_bet` | subdivisions 4 (default) | 0.9857 | 1,686,529 / 1,707,641 |
| bet2 `-f 0.5` | `run_bet` | subdivisions 5 | 0.9594 | 1,686,529 / 1,587,092 |

What the numbers say (owner of each: QSM.rs):
- **Best path matches.** Every voxel takes the same wrap count as scikit-image. 95.1 % are
  bit-identical; the rest differ by at most 9.1e-7 rad, rounding in the value, not a different
  unwrapping.
- **N4's 3 % is the shrink offset `n4.rs` documents.** This header's direction cosines carry an
  off-diagonal term of 4.9e-12. With it, ITK rounds the half-integer shrink offset
  (`(n−1)/2 − s·(m−1)/2` = 1.5 on every axis of 184×256×128 at shrink 4) the other way, so the bias
  field is fitted to samples one voxel apart. With the same voxels and an axis-aligned header (also
  with only the x flip, or only the origin), ANTs and QSM.rs agree to 0.002 % and 4.4e-5 of the
  maximum, as `n4.rs` reports. Scanner headers carry such terms, so matching ANTs needs the port to
  take the affine and compute the offset as ITK does.
- **BET's `subdivisions: 4` is bet2's `icosa(5)`.** `make_mesh_from_icosa(n)` is in the repository
  (`meshclass/mesh.cpp:210`), contrary to `evolution.rs:13-15`: it starts from the 12-vertex
  icosahedron and retessellates `n − 1` times, so `icosa(5)` has 2562 vertices, QSM.rs's
  `subdivisions: 4`. Subdivisions 5 agrees less. At the default level QSM.rs's masks are 0.6 %
  (`-f 0.2`) and 1.3 % (`-f 0.5`) larger than bet2's; that gap is in the evolution.
- **Gibbs is not DIPY's output.** QSM.rs unrings in 3-D, DIPY in 2-D slices (`slice_axis=2`). Both
  change the input by about the same (NRMSE vs input 4.59 % DIPY, 4.65 % QSM.rs) but differ from
  each other by 2.0 %, locally by 16 % of the maximum. Matching DIPY needs a 2-D slice-wise mode.
- **MP-PCA is not DIPY's output.** QSM.rs gives each voxel its own patch's estimate; DIPY averages
  the overlapping patches. They change the input by 1.83 % (DIPY) and 2.04 % (QSM.rs) and differ by
  0.97 %. Matching DIPY needs the overlapping-patch average.
- **WaveSep is close, not identical** (χ+ 0.11 %, χ− 1.08 %), on the synthetic case only; the
  phantom pair is for the parity workflow.
