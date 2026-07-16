#!/usr/bin/env bash
# QSM-CI submission — LPCNN (dipole stage), single orientation, CPU-only.
#
# LPCNN is a learned-proximal unrolled network for the QSM dipole inversion:
#   consumes  localfield.nii.gz (ppm), mask.nii.gz, params.json   ->   produces  chimap.nii.gz
#
# The physics data-consistency term needs a dipole kernel encoding the B0 direction + matrix
# size; only demo kernels ship in-repo, so recon.py GENERATES the kernel .npy from
# params.json (B0_dir + voxel_size + volume matrix size). Units: QSM-CI's localfield is ppm,
# but LPCNN/inference.py divides its phase input by (tesla*gamma), so recon.py writes the
# phase file in Hz (= ppm*tesla*gamma) to recover ppm inside the model. Inputs are handed to
# inference.py as .txt file-lists (phase_file/dipole_file/mask_file), which we build here.
#
# Acquisition parameters arrive as env vars (see CONTRACT.md):
#   $QSMCI_B0 (T)   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
ALGO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LPCNN_HOME="${LPCNN_HOME:-/opt/LPCNN}"

# LPCNN was trained at 7T; --tesla only accepts {3,7}. Snap B0 to the nearer supported field.
B0="${QSMCI_B0:-}"
if [ -z "$B0" ] && command -v jq >/dev/null 2>&1 && [ -f "$IN/params.json" ]; then
  B0="$(jq -r '.B0 // 7' "$IN/params.json")"
fi
B0="${B0:-7}"
TESLA=7
awk "BEGIN{exit !($B0 < 5)}" && TESLA=3

# Pretrained weights (both ~5 MB, committed in-repo). Bmodel is used by default; override
# with LPCNN_RESUME to select checkpoints/lpcnn_test_Emodel.pkl.
RESUME="${LPCNN_RESUME:-$LPCNN_HOME/checkpoints/lpcnn_test_Bmodel.pkl}"

WORK="$OUT/_lpcnn_work"
python3 "$ALGO_DIR/recon.py" "$IN" "$WORK" "$TESLA"

# inference.py resolves every path relative to its cwd: it READS data/numpy_data/... (train
# stats, via root_dir='data/') and WRITES its result under LPCNN/test_result/. The container
# runs as a non-root user, so $LPCNN_HOME is read-only — cd-ing there makes the test_result
# mkdir fail (Permission denied). Run from a writable dir under $OUT instead, staging the
# read-only inputs as symlinks: 'data/' and the LPCNN package files (inference.py + lib) are
# symlinked in, while LPCNN/test_result/ stays a real, writable directory so the cwd-relative
# output can be written (the script dir on sys.path lets `from lib...` resolve through the
# symlink). Single orientation => --number 1.
SAVE_NAME="_qsmci"
RUNDIR="$WORK/run"
mkdir -p "$RUNDIR/LPCNN"
ln -sf "$LPCNN_HOME/data" "$RUNDIR/data"
for f in "$LPCNN_HOME/LPCNN"/*; do
  [ "$(basename "$f")" = "test_result" ] && continue
  ln -sf "$f" "$RUNDIR/LPCNN/$(basename "$f")"
done
cd "$RUNDIR"
python3 LPCNN/inference.py \
  --number 1 \
  --tesla "$TESLA" \
  --model_arch lpcnn \
  --no_cuda \
  --save_name "$SAVE_NAME" \
  --phase_file "$WORK/phase_data.txt" \
  --dipole_file "$WORK/dipole_data.txt" \
  --mask_file "$WORK/mask_data.txt" \
  --resume_file "$RESUME"

# inference.py writes LPCNN/test_result/<ckpt_stem>/<arch><save_name>_qsm.nii.gz (cwd-relative).
CKPT_STEM="$(basename "$RESUME")"; CKPT_STEM="${CKPT_STEM%%.*}"
RESULT="$RUNDIR/LPCNN/test_result/$CKPT_STEM/lpcnn${SAVE_NAME}_qsm.nii.gz"
mkdir -p "$OUT"
cp "$RESULT" "$OUT/chimap.nii.gz"
rm -rf "$WORK"
echo "wrote $OUT/chimap.nii.gz"
