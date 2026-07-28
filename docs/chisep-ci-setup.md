# χ-separation in CI — setup + status

χ-separation methods score on a **separate phantom** from the QSM pipeline (they need χ+/χ− ground
truth and R2′/χ_total inputs), so CI routes them to a `chisep` dataset. The code routing is done; two
one-time steps below need doing to make it live.

## What's wired (code)
- **`scripts/pack_dataset.py`** — auto-detects a χ-sep phantom (has `Chimap-pos/neg`) and packs
  `inputs/{localfield,chimap,r2prime,phase,magnitude,mask,params}` + `groundtruth/{chi-para,chi-dia,chimap,dseg}`.
- **`scripts/fetch_dataset.sh`** — `chisep` track pulls its own bids.zip (`OSF_FILE_CHISEP`) and packs with χ-sep layout.
- **`.github/workflows/evaluate.yml`** — the per-PR job reads each changed method's `stage`; `chi-separation`
  → `chisep` dataset (`data/chisep/scoring`), everything else → the QSM `sim` phantom. Verified locally:
  chi-sepnet/susep-net → chisep, tkd/matlab-tkd → sim.

## One-time setup (needs your OSF token — publish steps)
1. **Upload the χ-sep phantom** `bids.zip` to OSF project `y8adf` (osfstorage). The packaged file is at
   `/tmp/chisep_bids.zip` (~303 MB; raw multi-echo GRE + `derivatives/qsm-forward` with the χ+/χ−/R2′ maps).
   The χ+/χ− ground truth is held-out (in the zip, never committed) — same as the QSM phantom.
2. **Set the repo secret `OSF_FILE_CHISEP`** to that file's OSF id. `evaluate.yml` reads it (empty →
   chi-sep PRs fail fetch with a clear message; QSM PRs unaffected).

## Container images (make public)
Both DL methods are pushed to GHCR; make each package **public** so CI can pull it:
- `ghcr.io/astewartau/qsm-ci/chi-sepnet:v1` — settings: `.../packages/container/qsm-ci%2Fchi-sepnet/settings`
- `ghcr.io/astewartau/qsm-ci/susep-net:v1` — settings: `.../packages/container/qsm-ci%2Fsusep-net/settings`

## Still TODO
- **`score.yml`** (the periodic full re-run / composition matrix) does NOT yet route chi-sep methods —
  it sweeps the QSM matrix only. Add a chisep leg (fetch chisep + isolated-only) once the dataset is up.
- The MATLAB chi-sep methods (chi-sep-ilsqr/medi, apart-qsm) need images built via `mcc` + matlab-runtime
  before CI can pull them; iLSQR is also pending the Bunya diagnostic (is it even fixable).

## Local verification done
`OSF_ZIP=/tmp/chisep_bids.zip fetch_dataset.sh chisep <dest>` produces the correct inputs+GT; the docker
images run offline and reproduce the scores (chi-sepnet 0.93/0.83, susep-net 0.83/0.88).
