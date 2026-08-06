# BUILD — DIP-UP (`dip-up`)

The run phase has **no network** (`--network none`), so both the method source **and the pretrained
checkpoints** must be baked into the image at build time. The Dockerfile:

1. installs a **CUDA** PyTorch wheel (also runs CPU-only via fallback);
2. `git clone`s `github.com/sunhongfu/DIP-UP` into `/opt/DIP-UP` (its `Unet_2Chan_9Class` /
   `Unet_1Chan_9Class` network classes are reused by the wrapper), pinned via `--build-arg DIPUP_REF`;
3. **downloads and unpacks the pretrained checkpoints** into `/opt/dip-up-weights`.

The reconstructed `Unet_blocks.py` (which the repo omits) and the wrapper are **mounted** at run time,
not COPYed — the standard QSM-CI execution model.

## Weights source (baked in)

Published by the authors on Dropbox. The **folder** URL with `dl=1` returns a zip of the two
checkpoints:

- `PHU-NET3D.pth` — ~262 MB (2-channel, width 64)
- `PhaseNet3D.pth` — ~148 MB (1-channel, width 48)

```
https://www.dropbox.com/scl/fo/r4qv54fsdznxxmqgdcwn0/AMCMT9M-hvgmZ276-hcgaV8?rlkey=di0g1drz4whpz308rn84cxnx9&dl=1
```

The Dockerfile fetches this (`DIPUP_WEIGHTS_URL` build-arg, overridable if the share link rotates),
unzips into `/opt/dip-up-weights`, and asserts both `.pth` files exist. **Verified downloadable**
(HTTP 200, 410 MB zip, `store`-compressed) and both checkpoints load with `strict=True` against the
reconstructed `Unet_blocks.py`.

## 1. Build & push the environment image

```bash
# from the repo root
docker build -t ghcr.io/astewartau/qsm-ci/dip-up:v1 algorithms/dip-up
docker push  ghcr.io/astewartau/qsm-ci/dip-up:v1
```

- The method commit is pinned by default (`DIPUP_REF=bae8a90469140841fb44f5b02555c1c45016932a`); override
  with `--build-arg DIPUP_REF=<sha>`.
- Override the weights URL with `--build-arg DIPUP_WEIGHTS_URL=...` if the Dropbox link rotates.
- QSM-CI also builds this folder's Dockerfile at score-time, so a manual push is not strictly required
  — but build it once locally to confirm the clone + weight download succeed.

### CPU-only variant (optional)

Change the torch install to the CPU index (`pip install "torch>=2.1.0" --index-url
https://download.pytorch.org/whl/cpu`) to shrink the image if no GPU runner is available. The wrapper
already falls back to CPU with the CUDA wheel, so this is only a size optimization.

## 2. Smoke-test locally (with ground truth)

The `local` pipeline runner executes `run.sh` directly (no Docker), so point the env at a local
checkout of the repo + weights and run on the dev phantom:

```bash
DIPUP_HOME=/path/to/DIP-UP DIPUP_WEIGHTS=/path/to/weights \
QSMCI_SET_ITERATIONS=100 QSMCI_SET_VARIANT=PHU-NET3D \
python algorithms/dip-up/dip_up_infer.py data/sim/dev/inputs /tmp/out

python eval/qsm_eval.py --recon /tmp/out/totalfield.nii.gz \
  --truth data/sim/dev/groundtruth/totalfield.nii.gz \
  --kind field --mask data/sim/dev/inputs/mask.nii.gz --out /tmp/score.json
```

Confirm it produces `totalfield.nii.gz` in ppm and inspect `correlation` / `nrmse`. See the README
**DOMAIN-SHIFT CAVEAT** — a poor score on the sim phantom may be a real transfer-gap finding.

## 3. Decisions the human must make ⚠️

- **GPU vs. CPU / iteration cap.** The test-time DIP loop runs **once per echo** on a large 3-D
  U-Net; the reference recommends a 16–24 GB GPU. Time a run first; use a GPU runner or lower
  `iterations` if CPU exceeds the CI limit.
- **Domain shift.** Decide whether the pretrained base net is expected to transfer to the sim
  phantom's wrap patterns, or whether this submission is primarily interesting on in-vivo-like data.
- **Variant.** `PHU-NET3D` (2-channel, paper default) vs `PhaseNet3D` (1-channel, lighter).

## 4. Files in this folder

| File | Role |
|------|------|
| `algorithm.yml` | Manifest: stage `field-mapping`, image, `run: bash run.sh`, `inputs: [phase, mask, params]`, parameters. |
| `Dockerfile` | CUDA PyTorch + clone DIP-UP + bake Dropbox checkpoints. Code is mounted, not COPYed. |
| `run.sh` | Picks device, calls `dip_up_infer.py /input /output`. |
| `dip_up_infer.py` | Loads base net + weights, DIP refinement per echo, echo-fit → ppm, writes `totalfield.nii.gz`. |
| `Unet_blocks.py` | Reconstructed U-Net blocks (repo omits this), byte-compatible with the checkpoints. |
| `README.md` | Method description, units, the `Unet_blocks` reconstruction, deviations, caveats. |
