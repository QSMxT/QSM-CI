# IR2QSM — build & publish the environment image (human step)

This submission's environment image has **not** been built or pushed (needs network + `ghcr.io`
registry access). The scaffold is complete; do the following to finish.

## 1. Build the image (bakes code + weights)

The `Dockerfile` clones the IR2QSM repo and downloads the pretrained checkpoint with `gdown` at build
time (build phase has network; run phase does not).

```bash
# from the repo root
docker build -t ghcr.io/astewartau/qsm-ci/ir2qsm:v1 algorithms/ir2qsm
```

The exact weights-download step baked into the Dockerfile is:

```dockerfile
ARG IR2QSM_GDRIVE_ID=1EGZGxdgVWI8r0RlyfjP-xQyOL88vLeDf
RUN gdown "$IR2QSM_GDRIVE_ID" -O /opt/IR2QSM/Evaluate/model_IR2Unet.pth \
 && test -s /opt/IR2QSM/Evaluate/model_IR2Unet.pth
```

i.e. it fetches `model_IR2Unet.pth` from Google Drive file id
`1EGZGxdgVWI8r0RlyfjP-xQyOL88vLeDf`
(https://drive.google.com/file/d/1EGZGxdgVWI8r0RlyfjP-xQyOL88vLeDf/view). The larger demo bundle
(id `1S4SkhB-Lqz1D3lf4Q5UHdrpimRo7udbL`) is NOT needed — it only adds demo data.

### If the plain `gdown <id>` fails

Google Drive occasionally blocks the confirm-token flow (quota / "can't scan for viruses"). Fallbacks:

```bash
# newer gdown syntax
gdown --id 1EGZGxdgVWI8r0RlyfjP-xQyOL88vLeDf -O model_IR2Unet.pth
# or the full URL with fuzzy matching
gdown --fuzzy "https://drive.google.com/file/d/1EGZGxdgVWI8r0RlyfjP-xQyOL88vLeDf/view" -O model_IR2Unet.pth
```

If Drive rate-limits the CI build entirely, download `model_IR2Unet.pth` once by hand, host it
somewhere durable (a GitHub Release on a fork, an OSF/HF bucket, etc.), and swap the `gdown` line for
a `curl -fSL`. This is the single biggest build-reliability risk — Google-Drive downloads are not
guaranteed reproducible.

## 2. Smoke-test locally before pushing

Generate a phantom with ground truth and run the isolated `dipole` stage:

```bash
qsm-forward simple /tmp/bids            # writes localfield/chi/mask under derivatives/qsm-forward/
qsm-ci run ir2qsm \
  --localfield /tmp/bids/.../localfield.nii.gz \
  --mask       /tmp/bids/.../mask.nii.gz \
  --params     /tmp/bids/.../params.json \
  --truth      /tmp/bids/.../chimap.nii.gz     # scores it with the CI scorer
```

Check:
- it produces `chimap.nii.gz` on the input grid/affine,
- susceptibility magnitudes look physical (roughly ±0.1–0.2 ppm in tissue),
- no CUDA errors (the `AddNoise` monkeypatch in `ir2qsm_infer.py` must keep everything on CPU).

Also confirm `strict=False` didn't silently drop weights:

```bash
docker run --rm ghcr.io/astewartau/qsm-ci/ir2qsm:v1 python - <<'PY'
import os, sys, torch, torch.nn as nn
sys.path.insert(0, os.environ["IR2QSM_CODE"])
import IR2Unet
net = nn.DataParallel(IR2Unet.IR2Unet())
sd = torch.load(os.environ["IR2QSM_CKPT"], map_location="cpu")
missing, unexpected = net.load_state_dict(sd, strict=False)
print("missing:", missing)          # expect [] (or only non-parametric buffers)
print("unexpected:", unexpected)
PY
```

If `missing` lists real conv/bn weights, the checkpoint key layout differs from the current
`IR2Unet` definition (e.g. repo moved on from the pinned ref) — pin `IR2QSM_REF` to the commit the
weights were trained against.

## 3. Push

```bash
docker push ghcr.io/astewartau/qsm-ci/ir2qsm:v1
```

QSM-CI also builds this folder's Dockerfile at score-time, so a manual push is not strictly required
for the leaderboard — but pushing avoids re-downloading the weights on every scorer.

## Risks / notes

- **Weights download reliability** — Google Drive confirm-token / quota (see fallbacks above). Biggest risk.
- **GPU-only op** — upstream `AddNoise` hardcodes `.to("cuda:0")` and runs at inference; the wrapper
  monkeypatches it to be CPU-safe. If upstream refactors `AddNoise`, re-check the patch still binds.
- **Non-deterministic output** — that inference-time `AddNoise` is a random draw (gated by
  `torch.rand(1) > 0.3`), so repeated runs differ slightly. Consider seeding torch or disabling the
  call; flag with the authors.
- **Torch drift** — image uses current CPU `torch>=2.1.0` vs the repo's torch 1.13; verify numerics.
- **1 mm isotropic** — no resampling is done; non-1mm challenge data may degrade results.
