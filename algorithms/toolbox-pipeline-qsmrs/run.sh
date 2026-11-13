#!/usr/bin/env bash
# QSM-CI submission: a whole toolbox pipeline as QSMxT runs it (`qsmxt run --pipeline <id>`), the
# candidate side of pipeline parity (QSMxT/QSM-CI#421).
#   consumes phase.nii.gz (rad, x,y,z,echo), magnitude.nii.gz, params.json; mask.nii.gz only with
#            `dataset_mask`
#   produces chimap.nii.gz (ppm); chi-para.nii.gz, chi-dia.nii.gz (ppm) from the χ-separation
#            pipelines
#   intermediates (when $QSMCI_INTERMEDIATES is set): the steps qsmxt wrote, under CONTRACT.md's
#            names (mask, totalfield, localfield, r2star, ...)
# qsmxt reads BIDS, so /input becomes a one-run BIDS dataset with a sidecar per echo, carrying what
# a scanner's sidecar would: the toolbox pipelines read the field strength, centre frequency and
# vendor from there. The pipeline id is the `pipeline` parameter (--set pipeline=medi-toolbox).
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

PIPELINE=qsmxt-defaults
DATASET_MASK=false
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.pipeline // empty' "$CFG"); [ -n "$V" ] && PIPELINE="$V"
  V=$(jq -r '.dataset_mask // empty' "$CFG"); [ -n "$V" ] && DATASET_MASK="$V"
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# --- NIfTI headers without Python (the qsmxt image has bash, coreutils, gzip and jq) -----------

# The first 540 bytes of a NIfTI (enough for a NIfTI-1 or NIfTI-2 header), gzipped or not.
header() {
  if [ "$(od -An -tx1 -N2 "$1" | tr -d ' \n')" = "1f8b" ]; then
    gzip -dc "$1" 2>/dev/null | head -c 540 || true
  else
    head -c 540 "$1"
  fi
}

# "nx ny nz srow_x srow_y srow_z" of a NIfTI, to tell whether two files share a grid.
grid() {
  local h="$WORK/grid.hdr"
  header "$1" > "$h"
  case "$(od -An -td4 -N4 "$h" | tr -d ' \n')" in
    348) echo "$(od -An -td2 -j42 -N6 "$h") $(od -An -tf4 -j280 -N48 "$h")" ;;
    540) echo "$(od -An -td8 -j24 -N24 "$h") $(od -An -tf8 -j400 -N96 "$h")" ;;
    *)   echo "unreadable" ;;
  esac | tr -s ' \n' '  '
}

same_grid() {
  awk -v a="$(grid "$1")" -v b="$(grid "$2")" 'BEGIN {
    n = split(a, x, " "); if (n != split(b, y, " ") || n < 15) exit 1
    for (i = 1; i <= n; i++) { d = x[i] - y[i]; if (d < 0) d = -d; if (d > 1e-3) exit 1 }
  }'
}

# Little-endian bytes of an integer, as printf escapes: $1 value, $2 width in bytes.
le_bytes() {
  local v=$1 n=$2 s="" i
  for ((i = 0; i < n; i++)); do s+=$(printf '\\x%02x' $(( (v >> (8 * i)) & 255 ))); done
  printf '%s' "$s"
}

# Split a 4-D NIfTI into 3-D volumes $2<n>.nii (n from 1) and print how many. Each is the input's
# header (extensions included) with dim[0] = 3 and dim[4] = 1, then that volume's bytes: the data
# are not decoded, so every value and the scaling stay exactly as given. A 3-D input is one echo.
split_echoes() {
  local raw="$WORK/split.nii" dimoff w voxoff bitpix d
  if [ "$(od -An -tx1 -N2 "$1" | tr -d ' \n')" = "1f8b" ]; then gzip -dc "$1" > "$raw"; else cp "$1" "$raw"; fi
  case "$(od -An -td4 -N4 "$raw" | tr -d ' \n')" in
    348) dimoff=40; w=2; voxoff=$(printf '%.0f' "$(od -An -tf4 -j108 -N4 "$raw")")
         bitpix=$(od -An -td2 -j72 -N2 "$raw" | tr -d ' \n') ;;
    540) dimoff=16; w=8; voxoff=$(od -An -td8 -j168 -N8 "$raw" | tr -d ' \n')
         bitpix=$(od -An -td2 -j14 -N2 "$raw" | tr -d ' \n') ;;
    *) echo "toolbox-pipeline-qsmrs: $1 is not a little-endian NIfTI-1 or NIfTI-2 file" >&2; return 1 ;;
  esac
  read -r -a d <<< "$(od -An -td$w -j$dimoff -N$((8 * w)) "$raw" | tr '\n' ' ')"
  local ne=1 i e f vol
  [ "${d[0]}" -ge 4 ] && ne=${d[4]}
  for ((i = 5; i <= d[0]; i++)); do
    [ "${d[$i]}" -le 1 ] || { echo "toolbox-pipeline-qsmrs: $1 has more than 4 dimensions" >&2; return 1; }
  done
  vol=$(( d[1] * d[2] * d[3] * bitpix / 8 ))
  for ((e = 1; e <= ne; e++)); do
    f="$2$e.nii"
    head -c "$voxoff" "$raw" > "$f"
    printf "$(le_bytes 3 $w)" | dd of="$f" bs=1 seek=$dimoff conv=notrunc status=none
    printf "$(le_bytes 1 $w)" | dd of="$f" bs=1 seek=$((dimoff + 4 * w)) conv=notrunc status=none
    tail -c +$(( voxoff + (e - 1) * vol + 1 )) "$raw" | head -c "$vol" >> "$f"
  done
  rm -f "$raw"
  echo "$ne"
}

# --- /input as BIDS ------------------------------------------------------------------------------

BIDS="$WORK/bids"; ANAT="$BIDS/sub-1/anat"
mkdir -p "$ANAT"
echo '{"Name": "QSM-CI input", "BIDSVersion": "1.10.0"}' > "$BIDS/dataset_description.json"
NP=$(split_echoes "$IN/phase.nii.gz" "$WORK/phase")
NM=$(split_echoes "$IN/magnitude.nii.gz" "$WORK/mag")
NT=$(jq '.TE | length' "$IN/params.json")
if [ "$NP" != "$NT" ] || [ "$NM" != "$NT" ]; then
  echo "toolbox-pipeline-qsmrs: phase has $NP echoes, magnitude $NM, params.json TE $NT" >&2
  exit 1
fi
cp "$WORK/phase1.nii" "$WORK/input-grid.nii"   # the grid every output must be on
# MagneticFieldStrength is what the scanner's sidecar says: `B0_nominal` where the dataset computed
# `B0` from the centre frequency (CONTRACT.md, params.json), else `B0`. Giving qsmxt the computed
# value would hide the difference between the nominal field and ImagingFrequency, which is one of
# the things pipeline parity checks. B0_dir is a QSMxT sidecar field (B0 in image coordinates).
for ((e = 1; e <= NT; e++)); do
  for part in phase mag; do
    base="$ANAT/sub-1_echo-${e}_part-${part}_MEGRE"
    gzip -c "$WORK/$part$e.nii" > "$base.nii.gz"
    rm -f "$WORK/$part$e.nii"
    jq --argjson e "$e" '{EchoTime: .TE[$e - 1], EchoNumber: $e,
          MagneticFieldStrength: (.B0_nominal // .B0), B0_dir}
        + (if .ImagingFrequency != null then {ImagingFrequency} else {} end)
        + (if .Manufacturer != null then {Manufacturer} else {} end)' \
      "$IN/params.json" > "$base.json"
  done
done

# A supplied R2′ (Hz), when the dataset has one: the χ-separation toolbox takes a measured R2′, and
# QSMxT's χ-separation pipelines use a supplied map (`--use-custom-r2prime`) rather than predicting
# one. It is an input, not a setting: the pipeline's settings are untouched.
R2P=()
derivative() {
  mkdir -p "$BIDS/derivatives/qsmci/sub-1/anat"
  echo '{"Name": "qsmci", "BIDSVersion": "1.10.0", "DatasetType": "derivative"}' \
    > "$BIDS/derivatives/qsmci/dataset_description.json"
}
if [ -f "$IN/r2prime.nii.gz" ]; then
  derivative
  cp "$IN/r2prime.nii.gz" "$BIDS/derivatives/qsmci/sub-1/anat/sub-1_R2primemap.nii.gz"
  R2P=(--use-custom-r2prime qsmci)
fi

# The dataset's brain mask in place of the one the pipeline makes, only when asked
# (`dataset_mask`): for a toolbox whose mask comes from data no pipeline input has (UK Biobank's,
# from its T1 pipeline), so both sides of the pair start from the same mask. The pipeline's
# settings are untouched; qsmxt uses a supplied mask as given (`--use-custom-masks`).
MASK=()
if [ "$DATASET_MASK" = true ]; then
  [ -f "$IN/mask.nii.gz" ] || { echo "toolbox-pipeline-qsmrs: dataset_mask needs mask.nii.gz" >&2; exit 1; }
  derivative
  cp "$IN/mask.nii.gz" "$BIDS/derivatives/qsmci/sub-1/anat/sub-1_mask.nii.gz"
  MASK=(--use-custom-masks qsmci)
fi

# --- the pipeline --------------------------------------------------------------------------------

# The pipeline option sets every reconstruction setting to the toolbox's; nothing else here
# changes one. `--output-space acquired` (QSMxT's default, given so a pipeline cannot change it)
# puts the outputs back on the input grid when qsmxt resampled to an axial one. stdin is closed so
# nothing can wait for an answer.
qsmxt run "$BIDS" "$WORK/out" --pipeline "$PIPELINE" --output-space acquired "${R2P[@]}" "${MASK[@]}" < /dev/null
D="$WORK/out/derivatives/qsmxt"

# The file qsmxt wrote under this name, wherever in its tree (published or workflow/); empty if none.
found() { find "$D" -name "$1" -o -name "$1.gz" | sort | head -n 1; }

# Copy a map to $2 (gzipped), refusing one on another grid.
put() {
  if ! same_grid "$1" "$WORK/input-grid.nii"; then
    echo "toolbox-pipeline-qsmrs: ${1#"$D"/} is not on the input grid" >&2
    return 1
  fi
  if [ "$(od -An -tx1 -N2 "$1" | tr -d ' \n')" = "1f8b" ]; then cp "$1" "$2"; else gzip -c "$1" > "$2"; fi
}

F=$(found sub-1_Chimap.nii)
[ -n "$F" ] || { echo "toolbox-pipeline-qsmrs: qsmxt wrote no Chimap" >&2; exit 1; }
put "$F" "$OUT/chimap.nii.gz"
F=$(found sub-1_desc-paramagnetic_Chimap.nii); [ -z "$F" ] || put "$F" "$OUT/chi-para.nii.gz"
F=$(found sub-1_desc-diamagnetic_Chimap.nii);  [ -z "$F" ] || put "$F" "$OUT/chi-dia.nii.gz"

# Intermediates: CONTRACT.md name <- qsmxt file. Every one is in ppm, Hz or 0/1 already. A map
# qsmxt left on its working (axial) grid is skipped with a note rather than resampled here: a
# resampling of ours would be a difference neither pipeline has.
if [ -n "${QSMCI_INTERMEDIATES:-}" ]; then
  mkdir -p "$QSMCI_INTERMEDIATES"
  while read -r name file; do
    F=$(found "$file")
    [ -n "$F" ] || continue
    put "$F" "$QSMCI_INTERMEDIATES/$name.nii.gz" 2>/dev/null \
      || echo "toolbox-pipeline-qsmrs: $name skipped: ${F#"$D"/} is on qsmxt's working grid" >&2
  done <<'MAP'
mask sub-1_mask.nii
totalfield sub-1_desc-totalppm_fieldmap.nii
localfield sub-1_localfield.nii
chimap_unreferenced sub-1_desc-unreferenced_Chimap.nii
r2star sub-1_R2starmap.nii
r2prime sub-1_R2primemap.nii
reliability sub-1_desc-echofit_mask.nii
vessel_mask sub-1_desc-vessels_mask.nii
localfield_stage1 sub-1_desc-stage1_localfield.nii
chimap_stage1 sub-1_desc-stage1_Chimap.nii
localfield_stage2 sub-1_desc-stage2_localfield.nii
chimap_stage2 sub-1_desc-stage2_Chimap.nii
MAP
  # A pipeline that inverts each echo (DECOMPOSE) publishes one χ map per echo.
  for ((e = 1; e <= NT; e++)); do
    F=$(found "sub-1_desc-echo${e}_Chimap.nii")
    [ -z "$F" ] || put "$F" "$QSMCI_INTERMEDIATES/chimap_echo$e.nii.gz" 2>/dev/null \
      || echo "toolbox-pipeline-qsmrs: chimap_echo$e skipped: not on the input grid" >&2
  done
fi
