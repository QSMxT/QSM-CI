# IR2QSM

A pretrained deep-learning network for quantitative susceptibility mapping by **dipole inversion**,
using **iterative Reverse Concatenations and Recurrent Modules** (an "IR2U-net").

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [IR2QSM](https://github.com/YangGaoUQ/IR2QSM) — PyTorch, **CPU-only** here (the repo
  targets Python 3.10+ / PyTorch 1.13+; a current CPU torch runs it fine with `CUDA_VISIBLE_DEVICES=-1`)
- **Reference:** Li M., Chen C., Xiong Z., Liu Y., Rong P., Shan S., Liu F., Sun H., Gao Y. (2025).
  *Quantitative susceptibility mapping via deep neural networks with iterative reverse concatenations
  and recurrent modules.* Medical Physics. (DOI: [10.1002/mp.17747](https://doi.org/10.1002/mp.17747);
  preprint [arXiv:2406.12300](https://arxiv.org/abs/2406.12300))

> **STATUS: scaffold — needs Docker image build + push to ghcr (human).**
> This folder is complete but the environment image has **not** been built or pushed, because that
> requires a network + registry access (Google-Drive weights download + `ghcr.io` push). No part of
> IR2QSM inference has been run here. See **BUILD.md** for the exact steps, and the "Assumptions to
> verify" section below for what to confirm on the first real run.

## Why `dipole`

IR2QSM is a single network that maps a **local (tissue) field** directly to **susceptibility** — it
performs only the dipole inversion, with no field-mapping or background-field-removal step. So it
consumes `localfield` and produces `chimap`, i.e. the `dipole` stage. (`Evaluate/test.py` loads one
network, feeds it the local field `lfs1.nii`, and saves the susceptibility output.)

## Units & normalization

The QSM-CI `localfield` is the local/tissue field already **in ppm** (normalized by B0) — the same
quantity IR2QSM was trained on (their `lfs`, the local field shift in ppm).

Unlike QSMnet / MoDL-QSM, IR2QSM applies **no dataset mean/std normalization**: the reference
`Evaluate/test_util.py` feeds the local field to the network **directly**, and there is no
`norm_factor` / `NormFactor` file anywhere in the repo. The output is likewise already in ppm — no
de-normalization is applied. The wrapper therefore passes the field straight through.

IR2QSM was trained at **1 mm isotropic**; the IR2U-net has `depth=4` (so `depth-1 = 3` max-pool /
deconv levels), meaning spatial dims must be divisible by **2³ = 8**. The reference zero-pads each
dimension up to a multiple of 8 (`zero_padding(image, 8)`); the wrapper replicates that centered
padding and crops back afterwards. The output is masked and written on the input NIfTI's
affine/header (voxel size + orientation preserved).

## Network output

`model(x)` returns `(latest_out, all_output)`:
- `latest_out` — the fully integrated final estimate (residual `x_out + input`). **This is what the
  reference and the wrapper keep.**
- `all_output[t]` — the per-iteration (T=4) intermediate estimates; the reference explicitly
  recommends using the final output rather than an intermediate.

## Differences from the reference inference (deliberate)

1. **Mask.** The reference derives a mask from the *padded field's* nonzero voxels (`image != 0`); we
   use the supplied QSM-CI `mask.nii.gz` (the canonical brain mask for this stage), applied after
   cropping back to the original grid.
2. **Affine.** The reference saves with `affine=np.eye(4)`, discarding geometry; we round-trip the
   input NIfTI's affine so voxel size + orientation carry through unchanged (matching `qsmnet`).
3. **GPU-only `AddNoise` (important).** `IR2Unet.forward` calls `AddNoise()` in the decoder
   **unconditionally** — it is *not* gated by `self.training` — and upstream `AddNoise()` hardcodes
   `.to("cuda:0")`, which raises on a CPU box. The wrapper monkeypatches `AddNoise` to a
   device-correct version (same additive-noise formula, on the tensor's own device) so CPU inference
   reproduces the reference behavior. **Note:** because this noise call fires at inference time,
   IR2QSM's output is **mildly stochastic** (a random draw gated by `torch.rand(1) > 0.3`); this is
   inherited from the upstream released code, not introduced here. If deterministic output is
   required, seed torch or disable that call — flag for the authors, as it looks like a leftover from
   the training-time noise-regularization scheme.

## How QSM-CI runs it

```bash
bash run.sh                      # -> python ir2qsm_infer.py localfield.nii.gz mask.nii.gz chimap.nii.gz
```

`ir2qsm_infer.py` drives the repo's `Evaluate/IR2Unet.IR2Unet` with the baked checkpoint
(`model_IR2Unet.pth`), which was saved from an `nn.DataParallel`-wrapped model (keys carry a
`module.` prefix), so the wrapper wraps identically and loads with `strict=False` — exactly as the
reference `test.py` does.

## Weights (baked at build time from Google Drive)

The pretrained checkpoint `model_IR2Unet.pth` lives on the authors' Google Drive (file id
`1EGZGxdgVWI8r0RlyfjP-xQyOL88vLeDf`). It is fetched with **`gdown`** at **build time** (network is on
during build, off at scoring) and placed at `/opt/IR2QSM/Evaluate/model_IR2Unet.pth`, so inference
runs fully offline (`--network none`). `gdown` handles Google Drive's large-file confirm-token. See
**BUILD.md** for the exact command.

## Parameters

IR2QSM has no runtime tunables — it uses fixed pretrained weights (tuning-free). Voxel size and
orientation are carried by the input NIfTI affine.

## Assumptions to verify (first real run)

Because nothing was executed here, confirm these when the image is first built and run:

1. **Input units = ppm local field.** Derived from the reference feeding `lfs1.nii` directly with no
   scaling. If IR2QSM's demo `lfs` turns out to be scaled differently (e.g. Hz, or a fixed ppm
   scaling), the wrapper would need a matching factor. Sanity-check output susceptibility magnitude
   (expect roughly ±0.1–0.2 ppm in tissue).
2. **Padding factor = 8.** Taken from `zero_padding(image, 8)` in `test_util.py`. Verify the net
   accepts the padded volume without a shape mismatch.
3. **`latest_out` is the intended product** (vs. `all_output[-1]`). The reference uses `latest_out`.
4. **`strict=False` load leaves no critical weights unloaded.** The reference uses it because of the
   `DataParallel` prefix; confirm there are no *unexpectedly* missing keys (which would silently leave
   parts of the net at init).
5. **1 mm isotropic.** The network is trained at 1 mm iso; on non-1mm data results may degrade. The
   QSM-CI challenge grid should be checked; no resampling is done here (matching qsmnet).
6. **Torch version.** The image installs current CPU `torch>=2.1.0`. Confirm the checkpoint loads and
   the 3D-conv / ConvTranspose / SRU ops behave numerically as on the authors' torch 1.13.
7. **Non-determinism** from the inference-time `AddNoise` (see above) — decide whether to seed/disable.

## Building the image

See **BUILD.md**. In short:

```bash
docker build -t ghcr.io/astewartau/qsm-ci/ir2qsm:v1 algorithms/ir2qsm
docker push  ghcr.io/astewartau/qsm-ci/ir2qsm:v1
```

_Citations/DOIs should be verified against the published paper._
