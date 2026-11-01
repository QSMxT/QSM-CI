# Deep-learning originals: fidelity and first look

QSMxT/QSM-CI#301, part of #295. QSM.rs runs the deep-learning models as ONNX exports of the
authors' trained weights. Each original runs here as its QSM-CI entry, whose pinned image holds the
authors' code and weights. Each port is the `<slug>-qsmrs` entry, which runs the same model through
qsmxt. The two entries share `algorithm:`, so the parity workflow can run them as a pair.

| original | QSM-CI entry | port (qsmxt) | port entry |
|---|---|---|---|
| xQSM | `xqsm` | `invert xqsm` | `xqsm-qsmrs` |
| QSMnet / QSMnet+ | `qsmnet`, `qsmnet-plus` | `invert qsmnet`, `invert qsmnet-plus` | `qsmnet-qsmrs`, `qsmnet-plus-qsmrs` |
| LPCNN | `lpcnn` | `invert lpcnn` | `lpcnn-qsmrs` |
| QSMGAN | `qsmgan` | `invert qsmgan` | `qsmgan-qsmrs` |
| MoDL-QSM | `modl-qsm` | `invert modl-qsm` | `modl-qsm-qsmrs` |
| IR2QSM | `ir2qsm` (`add_noise=false`) | `invert ir2qsm` | `ir2qsm-qsmrs` |
| AutoQSM | `autoqsm` | `invert autoqsm` | `autoqsm-qsmrs` |
| NeXtQSM | `nextqsm` | `invert nextqsm` | `nextqsm-qsmrs` |
| BFRnet | `bfrnet` | `bgremove bfrnet` | `bfrnet-qsmrs` |
| χ-sepnet | `chisepnet` | `separate chi-sepnet` | `chisepnet-qsmrs` |
| SUSEP-Net | `susep-net` | `separate susep-net` | `susep-net-qsmrs` |
| HD-BET | `hd-bet-qsmci` | `mask hd-bet` | `hd-bet-qsmrs` |
| MindGrab | none yet | `mask mindgrab` (QSMxT main only) | `mindgrab-qsmrs` (`ci_skip`) |
| iQSM / iQSM+ / iQFM | `iqsm`, `iqsm-plus`, `iqfm` | only through `qsmxt run` | none yet |
| R2PRIMEnet | `r2primenet` | only through `qsmxt run` | none yet |
| MoDIP, INR-QSM | `modip`, `inr-qsm` | not ported | |

The port entries run `qsmxt:v10.0.0-models-2`: the v10.0.0 release image with the ONNX weights baked
in ([`algorithms/_qsmxt/models.Dockerfile`](../../algorithms/_qsmxt/models.Dockerfile)), because a
submission runs with no network. The weights come from `qsmxt/qsm-onnx-weights` at commit
`f9a6681`, checked against the SHA-256s in QSM.rs's registry
([`models.sha256`](../../algorithms/_qsmxt/models.sha256)). That commit replaced `qsmnet.onnx`
with the ReLU re-export (astewartau/QSM.rs#374), the only file that differs from `acc6f02`, where
the earlier `v10.0.0-models` image was built (it holds the old leaky-ReLU `qsmnet.onnx`).
Any qsmxt image takes the same layer (`--build-arg BASE=<image>`), and the parity workflow's
qsmxt-from-source image needs it for these pairs.

## What is checked

1. **Pinned.** Every original's Dockerfile pins its source commit or PyPI version, its framework
   versions and its weights' SHA-256s. The pins are what the published image already holds, so no
   image was rebuilt and every score stands. The full `pip freeze` of each image is in
   [`results/freeze/`](results/freeze), and the hashes of every weight file are in
   [`results/weights.sha256`](results/weights.sha256). As a check of the pins, LPCNN was rebuilt
   from its pinned Dockerfile: the output is identical to the published image's.
2. **Deterministic.** Each image runs twice on the same inputs, with OMP/MKL/OpenBLAS/TensorFlow
   threads set to 4, and the outputs are compared bit for bit. Where they differ, the spread is the
   floor any comparison with that original has.
3. **First look.** Each original against its port, built from QSM.rs main, on the same inputs:
   NRMSE, r and max |Δ| inside the mask, or Dice for masks. These numbers are reported, never a gate.
   Limits belong in `parity/thresholds.yml`.

## Running it

```bash
# The case: prisma-bridge-run1's inputs, cut to a box, plus its fields from the pinned qsmxt entries.
python fidelity/dl/harness.py prepare --case data/harmonization/prisma-bridge-run1/inputs --out case
qsm-ci run romeo-qsmrs --phase case/phase.nii.gz --magnitude case/magnitude.nii.gz \
    --mask case/mask.nii.gz --params case/params.json -o case/ --runner podman
qsm-ci run vsharp-qsmrs --totalfield case/totalfield.nii.gz --mask case/mask.nii.gz \
    --params case/params.json -o case/ --runner podman
# Every original twice. IR2QSM twice more with its noise off.
python fidelity/dl/harness.py determinism --case case --out out --slugs xqsm,qsmnet,...
python fidelity/dl/harness.py determinism --case case --out out-noiseoff --slugs ir2qsm --set '{"add_noise": false}'
# χ-separation reads R2' and χ: r2primenet's and xqsm's outputs from above.
cp out/determinism/r2primenet/run1/r2prime.nii.gz out/determinism/xqsm/run1/chimap.nii.gz case/
python fidelity/dl/harness.py determinism --case case --out out --slugs chisepnet,susep-net
# First look against a qsmxt image: QSM.rs main + the weights layer.
docker build -f algorithms/_qsmxt/models.Dockerfile --build-arg BASE=<qsmxt main image> -t qsmxt-main-models algorithms/_qsmxt
python fidelity/dl/harness.py pair --case case --out out --image qsmxt-main-models \
    --pairs xqsm,qsmnet,...,iqsm:qsmxt-run,iqfm:qsmxt-run,r2primenet:qsmxt-run
```

`ref:qsmxt-run` pairs an original whose port qsmxt only exposes through `qsmxt run`. The case is
written out as a one-subject BIDS dataset, with the mask supplied as a derivative, no referencing,
no inhomogeneity correction and no resampling. That compares a pipeline, not just the network.

## Case

- Public travelling-head acquisition `prisma-bridge-run1` (Siemens Prisma, 2.89 T, 5 echoes, 1 mm).
- Cut to a 128×160×96 box centred on the mask (`prepare`'s default). The full 184×256×128 volume ran
  xQSM out of memory next to the other jobs on this 15 GB workstation.
- Total field: `romeo-qsmrs`. Local field: `vsharp-qsmrs`. Both are the pinned v10.0.0 entries.
- 1,495,078 mask voxels.
- MoDIP and INR-QSM optimise per subject (hours on a full volume), so they ran on a 32³ box, for 10
  and 2 epochs.
- Also on a 64³ box ([`results/determinism-64.json`](results/determinism-64.json),
  [`results/pair-64.json`](results/pair-64.json)), as a trial of the fixture sizes below.

## Results (2026-10-28; Intel Core i5-11500, podman)

### Pinning, before and after

| original | before | after (= what the image holds) |
|---|---|---|
| `qsmnet`, `qsmnet-plus` | `QSMNET_REF=master`; Drive checkpoints unchecked | SNU-LIST/QSMnet f8782ed (master's head); checkpoint SHA-256s |
| `lpcnn` | `clone --depth 1`; torch and packages unpinned | Sulam-Group/LPCNN dd1ef2b; torch 2.13.0, NumPy 2.4.4, …; checkpoint SHA-256s. Master has since moved to 39b7820, which adds only a uv environment |
| `qsmgan` | `clone --depth 1`; `numpy<1.20`, `scipy<1.6` | QSMGAN-LupoLab 521d202 (weight zips from fa4dd8f); NumPy 1.19.5, SciPy 1.5.4; `.pt` SHA-256s |
| `nextqsm` | `pip install nextqsm`, unpinned | nextqsm 1.0.6, TensorFlow 2.13.1; weight SHA-256s |
| `modip` | `MODIP_REF=master`; `torch>=2.1` | sunhongfu/MoDIP 59959f8 (master's head); torch 2.13.0, NumPy 2.2.6, … |
| `inr-qsm` | `INR_QSM_REF=main`; `torch>=2.1` | AMRI-Lab/INR-QSM a8f767a (main's head); torch 2.13.0, …; transfer-learning weight SHA-256 |
| `hd-bet-qsmci` | `pip install HD-BET`, torch unpinned | HD-BET 2.0.1, torch 2.13.0+cpu; checkpoint SHA-256 |
| `modl-qsm` | `clone --depth 1` | Ruimin-Feng/MoDL-QSM 111a493 (master's head); `logs/last.h5` SHA-256 |
| `ir2qsm` | no Dockerfile in the repo (built from `main`, checkpoint copied in by hand) | committed Dockerfile: IR2QSM 1ddb147, torch 2.5.1+cpu; checkpoint SHA-256 |

Already pinned by commit, with their contents recorded: `xqsm` 5d13b36, `autoqsm` b59f5e7, `iqsm` and
`iqfm` bb163ef, `iqsm-plus` a534d94. The Dockerfiles of `chisepnet`, `susep-net` and `r2primenet`
stay out of the repo, because their weights are not public. Their images' weight hashes and
packages are recorded in their `fidelity:` blocks and [`results/`](results).

The base images (`python:3.x-slim`) are pinned by tag, not digest, because the digest each image
was built from is not recorded. A rebuild can therefore change OS packages. Each entry's published
image stays pinned by digest in `image:`.

### Determinism (128×160×96, 4 threads)

| original | twice | note |
|---|---|---|
| xqsm, qsmnet, qsmnet-plus, lpcnn, qsmgan, modl-qsm, autoqsm, nextqsm, bfrnet, chisepnet, susep-net, hd-bet-qsmci, r2primenet, r2primenet-7t, iqsm, iqsm-plus, iqfm | identical | |
| ir2qsm, `add_noise=false` | identical | |
| ir2qsm, default (the authors' noise on) | **NRMSE 12.6 %**, r 0.992, max \|Δ\| 0.107 ppm | the decoder draws noise at inference |
| susep-net | identical; at 64³, 2e-5 % (max \|Δ\| 2e-7 ppm) | `recon.py` uses every CPU (`torch.set_num_threads(os.cpu_count())`), not the fixed count |
| inr-qsm (32³, 2 epochs, seeded) | 0.017 %, max \|Δ\| 1.5e-5 ppm | CPU PyTorch's run-to-run floor |
| modip (32³, 10 epochs) | **81 %**, r 0.68 | unseeded random start; not deterministic, by design |

**IR2QSM's authors' default is noise on.** `IR2Unet.forward` adds noise in the decoder at
inference with probability 0.7 per iteration, and nothing gates it on `self.training`. The `ir2qsm`
entry keeps that default for scoring. The new `add_noise` parameter (`--set add_noise=false`) makes
every AddNoise call the identity. That is the branch QSM.rs's export pins, so it is the setting
parity compares against.

### First look against QSM.rs main da928e0 (in vivo, inside the mask; not a gate)

| original | port | NRMSE % | r | max \|Δ\| | max \|Δ\| / max \|ref\| |
|---|---|---|---|---|---|
| xqsm | xqsm-qsmrs | 0.00042 | 1.000000 | 3.2e-5 ppm | 0.0007 % |
| **qsmnet** | qsmnet-qsmrs | **126** | 0.759 | 0.51 ppm | 39 % |
| qsmnet-plus | qsmnet-plus-qsmrs | 0.00020 | 1.000000 | 4.1e-6 ppm | 0.0003 % |
| lpcnn | lpcnn-qsmrs | 0.00003 | 1.000000 | 7.7e-7 ppm | 0.00006 % |
| qsmgan | qsmgan-qsmrs | 0.00016 | 1.000000 | 1.6e-5 ppm | 0.004 % |
| modl-qsm | modl-qsm-qsmrs | 3.83 | 0.99926 | 0.0042 ppm | 0.28 % |
| ir2qsm (`add_noise=false`) | ir2qsm-qsmrs | 0.00018 | 1.000000 | 1.4e-5 ppm | 0.0003 % |
| autoqsm | autoqsm-qsmrs | 0.00013 | 1.000000 | 3.4e-7 ppm | 0.00007 % |
| nextqsm | nextqsm-qsmrs | 0.97 (64³: 3.1) | 0.99995 | 0.033 ppm | 3.3 % |
| bfrnet | bfrnet-qsmrs | 0.56 (64³: 0.00013) | 0.99998 | 0.0071 ppm | 0.93 % |
| chisepnet χ+ / χ− | chisepnet-qsmrs | 2.49 / 1.51 | 0.99958 / 0.99982 | 0.29 / 0.14 ppm | 13 / 6.5 % |
| susep-net χ+ / χ− | susep-net-qsmrs | 0.00003 / 0.00002 | 1.000000 | 1.9e-6 ppm | 0.00005 % |
| iqsm | `qsmxt run --qsm-algorithm iqsm` | 19.6 | 0.982 | 0.74 ppm | 55 % |
| iqsm-plus | `qsmxt run --qsm-algorithm iqsm-plus` | 20.7 | 0.980 | 0.80 ppm | 68 % |
| iqfm | `qsmxt run --bf-algorithm iqfm` | 20.8 | 0.976 | 0.29 ppm | 70 % |
| r2primenet | `qsmxt run --r2prime-strategy r2primenet` | 33.5 | 0.956 | 821 Hz | 62 % |

| original | port | Dice | voxels (original / port) |
|---|---|---|---|
| hd-bet-qsmci | hd-bet-qsmrs, both on the RSS-combined magnitude | 0.9891 | 1,496,770 / 1,465,490 |

**Findings**
- **QSMnet: the port doesn't match** (owner: QSM.rs). It gives 126 % NRMSE, and the port's χ is
  about 1.38 × the original's. QSMnet+ goes through the same code (the same constants as
  `norm_factor_*.mat`, `QsmnetNorm`) and matches to 2e-4 %. So the gap is in `qsmnet.onnx`, not the
  glue: the export doesn't reproduce the `QSMnet_64-25` checkpoint that the original runs.
- **BFRnet:** both run the same ONNX file. The original's wrapper tiles a volume larger than 128³
  into 128³ patches with 32 voxels of overlap, to save memory; QSM.rs runs the whole volume. On the
  64³ box neither tiles, and they agree to 1e-4 %. A pair should run the original with
  `patch_size=0`.
- **χ-sepnet:** the original runs SNU's fixed-patch `240904_xsepnet.onnx` (192×192×128, 75 % stride,
  averaged). QSM.rs runs its own export, whose hash differs. 1.4–2.5 % apart; not investigated here.
- **MoDL-QSM** is 3.4–3.8 % apart and **NeXtQSM** 1–3 %, on both boxes. Not investigated here
  (owner: QSM.rs).
- **HD-BET:** with the same RSS input, the port's mask is 2 % smaller (Dice 0.989).
  `hd-bet-qsmrs` itself gives `qsmxt mask hd-bet` the 4-D magnitude, and `qsmxt mask` then reads
  only the first echo, where `hd-bet-qsmci` combines the echoes by RSS (owner: QSMxT: `qsmxt mask`
  takes the first volume of a 4-D image without saying so).
- **iQSM, iQSM+, iQFM, R2PRIMEnet** are only reachable through `qsmxt run`, so the comparison
  includes qsmxt's phase scaling, echo handling and R2* fit. The 20–34 % gaps are those of a
  pipeline, not of a network. A `-qsmrs` entry for each needs a qsmxt subcommand that takes the
  stage's inputs (owner: QSMxT): `invert iqsm|iqsm-plus` from phase, `bgremove iqfm`, and R2′ from
  R2PRIMEnet. The qsmxt image has no tool to split a 4-D phase into the per-echo BIDS files that
  `qsmxt run` reads.
- **Speed:** qsmxt is slower than the originals on this box, at 4 threads: xQSM 108 s against 20 s,
  BFRnet 201 s against 48–68 s, NeXtQSM 222 s against 29–88 s.

## Fixtures for QSM.rs#317

The manual tests in `tests/models_onnx.rs` read references from local paths. Each can become a
fixture test, generated by the verified image of its original:

```bash
python fidelity/dl/harness.py prepare --case case --out fx64 --size 64x64x64
python fidelity/dl/harness.py determinism --case fx64 --out fx --slugs <slug>   # fx/determinism/<slug>/run1/
```

All of these were generated this way, and checked against the ports, on the 64³ box
([`results/pair-64.json`](results/pair-64.json)).

| test | fixture input (64³, float32, about 1 MB a volume) | generator | runtime |
|---|---|---|---|
| `xqsm_`, `qsmnet_`, `qsmnet_plus_`, `lpcnn_`, `qsmgan_`, `modl_qsm_matches_python_reference` | localfield, mask | `--slugs xqsm` (etc.) | 3–11 s |
| `ir2qsm_matches_python_reference` | localfield, mask | `--slugs ir2qsm --set '{"add_noise": false}'` | 3 s |
| `autoqsm_matches_keras_reference`, `nextqsm_matches_python_reference` | totalfield, mask | `--slugs autoqsm` / `nextqsm` (64³ is NeXtQSM's divisor) | 7–10 s |
| `bfrnet_matches_python_reference` | totalfield, mask | `--slugs bfrnet` (fits one patch, so no tiling) | 4 s |
| `chisepnet_`, `susep_net_matches_python_reference` | localfield, chimap, r2prime, mask | `--slugs chisepnet` / `susep-net` (χ and R2′ cut from the 128×160×96 box's `xqsm` and `r2primenet` outputs) | 6–9 s |
| `r2primenet_matches_python_reference` | magnitude (5 echoes), mask, params | `--slugs r2primenet` | 11 s |
| `iqsm_`, `iqsm_plus_`, `iqfm_matches_python_reference` | phase, magnitude (5 echoes), mask, params | `--slugs iqsm` / `iqsm-plus` / `iqfm` | 3–6 s |
| `hdbet_matches_python_reference` | RSS magnitude of the 128×160×96 box (on the 64³ box the masks agree to Dice 0.09: HD-BET needs the head) | `--slugs hd-bet-qsmci` | 17 s |
| `mindgrab_matches_brainchop`, `rs2net_matches_python_reference` | no original in QSM-CI yet | keep the Bunya references until one exists | |

Fixtures should store the original's output (float32), and the test should assert NRMSE, r and
max |Δ| against limits set from the numbers above. For QSMnet, the limit should wait until the
export is fixed.

## Not done here

- **Originals for SynthSeg, MindGrab and RS2-Net.**
  - MindGrab would be a `brain-extraction` entry. Its original is brainchop. The Python
    brainchop-cli drops the trained head bias, so a faithful image needs the web brainchop's model
    and code, not the CLI.
  - SynthSeg would be a fixture run, since segmentation is not a QSM-CI stage.
  - RS2-Net would be a fixture run too, and it needs a rodent case; QSM-CI has none.
- **GPU-only entries** (`after-qsm`, `dip-up`) are out of scope.
- **An Actions job for these runs.** The parity workflow runs the stage pairs; it needs the weights
  layer on its qsmxt image.
