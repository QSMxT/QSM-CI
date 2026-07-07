# qsm-eval

The QSM-CI scorer. Loads a reconstruction and the held-out ground truth, computes the challenge
metrics, and writes `metrics.json` (plus optional slice figures).

Metrics come from **QSM.rs** (`qsm_core::metrics`) — the exact code the QSM.rs CI uses — so a run's
QSM-CI score matches what QSM.rs reports for the same data. There is a single source of truth.

## Prerequisite

`qsm_core::metrics` must be a **public** module in QSM.rs. This depends on the companion change
"promote the test-only metrics in `tests/common/mod.rs` into a public `src/metrics.rs`". Until that
lands, `eval/Cargo.toml` points at a local `path = "../../../QSM.rs"` checkout; switch it to a pinned
`git` rev before building the published image.

## Usage

```bash
cargo run -p qsm-eval -- \
  --recon out/chimap.nii.gz \
  --truth gt/chimap.nii.gz \
  --seg   gt/dseg.nii.gz \
  --mask  data/sim/public/mask.nii.gz \
  --track sim \
  --name  example-tkd \
  --runtime 42 \
  --out metrics.json \
  --figures figures/
```

- `--track sim` → full suite (region NRMSE, DGM linearity, calcification, streak, correlation, XSIM).
- `--track invivo` → correlation + XSIM only (phantom-only metrics omitted).

## Output

`metrics.json`:

```json
{
  "contract": "v1",
  "name": "example-tkd",
  "track": "sim",
  "runtime_s": 42.0,
  "metrics": {
    "nrmse": 15.2, "nrmse_detrend": 12.4, "nrmse_tissue": 8.9,
    "nrmse_blood": 22.1, "nrmse_dgm": 18.5, "dgm_linearity": 0.02,
    "calc_moment_dev": 0.46, "calc_streak": 0.12,
    "correlation": 0.75, "xsim": 0.81
  }
}
```
