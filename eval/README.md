# qsm-eval

The QSM-CI scorer. Loads a reconstruction and the held-out ground truth, computes the challenge
metrics, and writes `metrics.json` (plus an optional slice figure).

Implemented in Python (numpy/scipy/nibabel) so contributors can read and patch the metrics easily,
and so the scorer has no build coupling to any reconstruction library.

## Faithful port — keep in sync

The metrics are a 1:1 port of the QSM.rs reference implementation
(`tests/common/mod.rs` in https://github.com/astewartau/QSM.rs): `nrmse_challenge`, `correlation`,
`xsim` (5×5×5 XSIM), `dgm_linearity`, `dilate_mask_3d`, and `calcification_metrics`. Because it is a
*second* implementation, it must not drift:

- `test_metrics.py` pins the invariants.
- `qsm_eval.py --selfcheck` runs quick sanity checks.
- Before the challenge opens, add a fixture that cross-checks these numbers against QSM.rs on the
  actual phantom (identical inputs ⇒ identical scores to floating-point tolerance).

## Usage

```bash
pip install -r requirements.txt

# score a chi map (dipole/end-to-end output) — full suite with a segmentation
python qsm_eval.py \
  --recon out/chimap.nii.gz --kind chi \
  --truth gt/chimap.nii.gz --seg gt/dseg.nii.gz \
  --mask  ../data/sim/dev/inputs/mask.nii.gz \
  --stage dipole --name tkd --runtime 42 \
  --out metrics.json --figures figures/

# score a field map (field-mapping / bfr output)
python qsm_eval.py --recon out/localfield.nii.gz --kind field \
  --truth gt/localfield.nii.gz --mask ../data/sim/dev/inputs/mask.nii.gz \
  --stage bfr --name sharp --out metrics.json
```

- `--kind chi` with `--seg` → full suite (region NRMSE, DGM linearity, calcification, streak,
  correlation, XSIM). Without `--seg` (e.g. in-vivo) → correlation + XSIM only.
- `--kind field` → demeaned/detrended NRMSE, correlation, XSIM (region metrics don't apply to fields).

Usually you don't call this directly — `scripts/pipeline.py` drives it per produced artifact.

## Output

`metrics.json` (NaN metrics serialize as `null`):

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
