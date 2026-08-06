# DIP-UP

Deep-learning **phase unwrapping** — a **pretrained** 3-D CNN wrap-count predictor plus a **test-time
Deep-Image-Prior (DIP)** refinement — packaged as a QSM-CI **field-mapping** submission.

- **Stage:** `field-mapping` (multi-echo phase → totalfield, ppm)
- **Engine:** [DIP-UP](https://github.com/sunhongfu/DIP-UP) — PyTorch. **GPU-capable, CPU-optional**
  (the reference recommends a 16–24 GB GPU — see RUNTIME/GPU CAVEAT).
- **Reference:** Zhu X., Gao Y., Xiong Z., Jiang W., Liu F., Sun H. *DIP-UP: Deep Image Prior for
  Unwrapping Phase.* Information 2025, 16(7), 592.
  DOI: [10.3390/info16070592](https://doi.org/10.3390/info16070592)

## What it does

DIP-UP **unwraps a single echo** of wrapped GRE phase. A pretrained 3-D U-Net predicts, per voxel, a
9-class softmax over the integer **wrap count**; the expected count (shifted by `shift_base`, masked)
times 2π is added back to the wrapped phase to give the unwrapped phase. A **test-time DIP loop** then
fine-tunes that same network on the specific input under two unsupervised losses — a
**Laplacian-consistency** loss (the unwrapped phase should share the wrapped phase's Laplacian) and a
**masked total-variation** loss — so no labels are needed at test time. Two pretrained base variants
ship as checkpoints:

| Variant | Input channels | Width | Params | Checkpoint |
|---------|----------------|-------|--------|------------|
| **PHU-NET3D** (default) | 2 — `[wrapped phase, Laplacian(wrapped phase)]` | 64 | 68.7 M | `PHU-NET3D.pth` (262 MB) |
| **PhaseNet3D** | 1 — `[wrapped phase]` | 48 | 38.7 M | `PhaseNet3D.pth` (148 MB) |

## Why `field-mapping`, and how the total field is built

DIP-UP itself outputs **unwrapped phase for one echo** — it does **not** produce a total field, which
is what the `field-mapping` stage is scored on. So this wrapper:

1. runs DIP-UP (pretrained net + DIP refinement) on **each echo** of the input phase, giving unwrapped
   phase per echo;
2. performs the standard **per-voxel linear fit** of unwrapped phase vs TE — `slope =
   cov(TE, φ)/var(TE)` (rad/s) — and normalizes Hz → ppm by `B0` (`GAMMA = 42.576 MHz/T`).

Steps (2) are **identical** to `algorithms/laplacian-fieldmap/recon.py` and
`algorithms/romeo-fieldmap/recon.py`; only the unwrap operator (Laplacian/ROMEO → DIP-UP) changes.
This is exactly what is being benchmarked: DIP-UP's unwrap swapped into the reference field-mapping
pipeline. Output `totalfield.nii.gz` (ppm) is written on the input phase affine.

## Units & I/O

- **Input.** `phase.nii.gz` (multi-echo, radians, wrapped), `mask.nii.gz`, `params.json` (`TE`, `B0`).
- **Output.** `totalfield.nii.gz` — total off-resonance field in **ppm**, on the input affine.
- No unit rescale of the phase (DIP-UP operates directly on wrapped radians).

## The reconstructed `Unet_blocks.py`

The DIP-UP repo's network classes (`PhaseNet3D/Unet_1Chan_9Class.py`,
`PHU-NET3D/Unet_2Chan_9Class.py`) both `from Unet_blocks import *`, **but the repo does not ship
`Unet_blocks.py`** — it lived only in the authors' private xQSM/deepMRI tree. This submission ships a
**reconstructed `Unet_blocks.py`** (`EncodingBlocks`, `MidBlocks`, `DecodingBlocks`) that is
**byte-compatible with the released `.pth` state_dicts** — every checkpoint key and tensor shape
matches, and both checkpoints load with `strict=True`. Two further mismatches are handled in
`dip_up_infer.py`: the repo files hard-code `initial_num_layers` (64/32) whereas the **released**
nets are width **64 (PHU-NET3D)** / **48 (PhaseNet3D)**, so the constant is patched per variant before
the class is built.

## Implementation notes & deviations from the reference

The DIP losses (`_tv_loss`, `_lap_loss`) and the wrap-count decoding (9-class softmax → expected count
→ `·2π + wrapped`) are ported from the repo's `inference.py` / `Demo_DIP_*.py`. Deviations, all
documented so behavior is explicit:

1. **Iterations reduced.** The repo's demo runs **2000** DIP iterations per volume; the default here
   is **`iterations=100`** as a runtime knob (raise for closer fidelity — see RUNTIME/GPU CAVEAT).
   The refinement runs **once per echo**, so cost scales with `iterations × echoes`.
2. **PHU-NET3D's Laplacian channel is computed in Python.** The repo loaded a precomputed
   `wph_lap*.mat`; here the 2nd input channel is a discrete 3-D Laplacian of the wrapped phase
   (`_laplacian3d`). This matches the intent (wrapped-phase Laplacian) but is not byte-identical to
   the repo's `.mat` Laplacian.
3. **`tv_weight` exposed.** The reference loss is `TV + Laplacian` (unit TV weight). `tv_weight` is
   exposed for experimentation; the reference value is `1.0` and is not tuned.
4. **No `net(...)*10000` softmax temperature.** `Demo_DIP_PHUNET3D.py` scales logits by 1e4 before the
   softmax; `inference.py` (the repo's cleaned entry point) does not. We follow `inference.py`
   (plain softmax). This only sharpens the class distribution; the rounded final count is unchanged in
   the typical case.

## RUNTIME / GPU CAVEAT ⚠️

The test-time DIP loop fine-tunes a large 3-D U-Net **once per echo**. The reference recommends a
**16–24 GB GPU**. Consequences for QSM-CI:

- On **CPU** (fallback here) this is **slow**; with 4 echoes and non-trivial `iterations` a CPU run
  can approach or exceed the CI time limit. Use a **GPU runner** (`QSMCI_GPU=1` passes `--nv`/`--gpus`)
  or lower `iterations` for a CPU smoke test.
- Device is chosen at run time: GPU when visible, else CPU; force CPU with `QSMCI_FORCE_CPU=1`.

## DOMAIN-SHIFT CAVEAT (main scientific risk) ⚠️

The base net is **pretrained on real brain GRE phase** at a specific resolution / TE (sim 10 ms,
in-vivo 5.8 ms) / field strength. QSM-CI's **simulation phantom** has different wrap patterns and
per-echo TEs (e.g. `TE = [4, 12, 20, 28] ms`), so the pretrained **wrap-count predictor may not
transfer**. The DIP refinement helps but is **seeded** by the base net's prediction. **A poor
field-mapping score here can reflect this transfer gap, not an implementation bug** — this is a
legitimate finding and should be reported with numbers, not tuned away.

**What we measured on `data/sim/dev` (CPU smoke test, PhaseNet3D).** The pretrained **base net alone**
(`iterations=0`) does NOT transfer to the phantom: totalfield correlation ≈ **−0.12** (full volume) /
**−0.19** (48³ crop), NRMSE > 2300%. But the **test-time DIP refinement rescues it**: with just
`iterations=30` on the 48³ crop, correlation rises to **+0.63** and NRMSE to **123%** — on par with
the reference Laplacian field-mapping (corr +0.62, NRMSE 95% on the full volume). So the useful signal
here comes from the **DIP optimization**, not the transferred wrap-count prior. More iterations (the
repo uses 2000) and the full volume are expected to improve this further; those runs are GPU-scale
(see RUNTIME/GPU CAVEAT) and were not completed on the CPU smoke box.

## Parameters (`algorithm.yml`)

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `variant` | `PHU-NET3D` | Base net: `PHU-NET3D` (2-ch, width 64, paper default) or `PhaseNet3D` (1-ch, width 48). |
| `iterations` | 100 | Test-time DIP iterations **per echo** (repo demo: 2000). Main runtime knob. |
| `lr` | 1e-6 | RMSprop learning rate (reference default). |
| `lr_decay` | 1 | Reference 'vlr' schedule: ×0.9 every 10 iters (1 = on, 0 = constant). |
| `tv_weight` | 1.0 | Weight on the masked-TV term of the DIP loss (reference 1.0). |
| `shift_base` | 5 | Wrap-class zero-offset (reference default). |

Overrides arrive via `/input/config.json` or `QSMCI_SET_*` (e.g. `QSMCI_SET_ITERATIONS=200`).

## How QSM-CI runs it

```bash
bash run.sh                       # -> python dip_up_infer.py /input /output
```

## Files in this folder

| File | Role |
|------|------|
| `algorithm.yml` | Manifest: stage `field-mapping`, image, `run: bash run.sh`, `inputs: [phase, mask, params]`, parameters. |
| `Dockerfile` | CUDA-capable PyTorch base + `git clone` DIP-UP + **bake the Dropbox checkpoints** into the image. Code is mounted, not COPYed. |
| `run.sh` | Picks device (GPU/CPU), calls `dip_up_infer.py /input /output`. |
| `dip_up_infer.py` | Loads the base net + weights, runs DIP refinement per echo, echo-fit → ppm, writes `totalfield.nii.gz`. |
| `Unet_blocks.py` | **Reconstructed** U-Net blocks, byte-compatible with the released checkpoints (the repo omits this file). |
| `README.md`, `BUILD.md` | This file and the build/push instructions. |
