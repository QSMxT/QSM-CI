#!/usr/bin/env bash
# Validate qsm-eval against QSM.rs's own ChallengeMetrics on the SAME recon/truth/mask/seg.
# Both are ports of the same algorithm; this proves they agree numerically (drift guard).
#
# Requires: a QSM.rs checkout containing tests/crosscheck.rs (set QSM_RS), and a packed dataset.
# Usage: scripts/crosscheck_qsmrs.sh [dataset-dir]     (default data/sim/scoring)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QSM_RS="${QSM_RS:-$HOME/repos/qsm/QSM.rs}"
DATASET="${1:-$ROOT/data/sim/scoring}"
TOL="${TOL:-1e-6}"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

[ -f "$QSM_RS/tests/crosscheck.rs" ] || { echo "need QSM.rs with tests/crosscheck.rs (set QSM_RS)"; exit 1; }

# 1. produce a real recon: TKD on the ground-truth local field boundary
mkdir -p "$tmp/in" "$tmp/out"
cp "$DATASET/groundtruth/localfield.nii.gz" "$tmp/in/localfield.nii.gz"
cp "$DATASET/inputs/mask.nii.gz"            "$tmp/in/mask.nii.gz"
cp "$DATASET/inputs/params.json"            "$tmp/in/params.json"
python3 "$ROOT/algorithms/tkd/recon.py" "$tmp/in" "$tmp/out"

# 2. normalize the 4 compared files to scl_slope=1 (avoid any reader scaling ambiguity)
python3 - "$tmp" "$DATASET" <<'PY'
import sys, nibabel as nib, numpy as np
tmp, ds = sys.argv[1], sys.argv[2]
srcs = {"recon": f"{tmp}/out/chimap.nii.gz", "truth": f"{ds}/groundtruth/chimap.nii.gz",
        "mask": f"{ds}/inputs/mask.nii.gz", "seg": f"{ds}/groundtruth/dseg.nii.gz"}
for k, p in srcs.items():
    im = nib.load(p); d = np.asarray(im.get_fdata(), np.float32)
    ni = nib.Nifti1Image(d, im.affine); ni.header.set_slope_inter(1, 0)
    nib.save(ni, f"{tmp}/{k}.nii.gz")
PY

# 3. Python metrics (qsm-eval)
python3 "$ROOT/eval/qsm_eval.py" --recon "$tmp/recon.nii.gz" --kind chi \
  --truth "$tmp/truth.nii.gz" --seg "$tmp/seg.nii.gz" --mask "$tmp/mask.nii.gz" \
  --out "$tmp/py.json" >/dev/null

# 4. Rust metrics (QSM.rs ChallengeMetrics via tests/crosscheck.rs)
( cd "$QSM_RS" && CC_RECON="$tmp/recon.nii.gz" CC_TRUTH="$tmp/truth.nii.gz" \
  CC_MASK="$tmp/mask.nii.gz" CC_SEG="$tmp/seg.nii.gz" \
  cargo test --test crosscheck -- --nocapture 2>/dev/null ) | sed -n 's/^CC_JSON //p' > "$tmp/rs.json"

# 5. compare
python3 - "$tmp/py.json" "$tmp/rs.json" "$TOL" <<'PY'
import json, sys
py = json.load(open(sys.argv[1]))["metrics"]; rs = json.load(open(sys.argv[2])); tol = float(sys.argv[3])
worst = 0.0
for k in py:
    rel = abs(py[k] - rs[k]) / (abs(rs[k]) or 1.0); worst = max(worst, rel)
    print(f"  {k:16} py={py[k]:.10g}  rust={rs[k]:.10g}  rel={rel:.1e}")
print(f"max relative difference: {worst:.2e}  (tol {tol:.0e})")
sys.exit(0 if worst < tol else 1)
PY
echo "cross-check PASSED: qsm-eval is numerically identical to QSM.rs"
