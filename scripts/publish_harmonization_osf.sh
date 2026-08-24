#!/bin/bash
# Upload the harmonization dataset to OSF via the WaterButler API (osfclient's recursive upload
# is broken — parent._new_file_url NoneType on nested folders).
#
#   qsmci-inputs/<acq>.zip   one prepacked zip per acquisition (inputs/ at zip root, the layout
#                            fetch_dataset.sh `prepacked: true` expects) — 23 zips
#   raw/<scanner>-<protocol>.zip  the raw exports incl. corrected sidecars — 8 zips
#   raw/{README.md,protocols.json,*.pdf}  top-level docs
#
# Zips are built one at a time in $TMPDIR and deleted after upload (the local disk is tight).
# Every uploaded file's WaterButler id is appended to results/osf_harmonization_files.json so the
# registry (scripts/datasets.json osf_file) can be wired afterwards.
#
# Usage:
#   OSF_TOKEN=<personal-access-token> ./scripts/publish_harmonization_osf.sh <osf-project-id>
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT=${1:?usage: OSF_TOKEN=... $0 <osf-project-id>}
: "${OSF_TOKEN:?set OSF_TOKEN (https://osf.io/settings/tokens)}"
API="https://files.osf.io/v1/resources/$PROJECT/providers/osfstorage"
AUTH=(-H "Authorization: Bearer $OSF_TOKEN")
MAP=scripts/osf_harmonization_files.json
TMP=${TMPDIR:-/tmp}

# mkfolder <name> -> folder path id ("" on root); idempotent (409 -> look the folder up)
mkfolder() {
    local name=$1 out
    out=$(curl -sS "${AUTH[@]}" -X PUT "$API/?kind=folder&name=$name")
    local id
    id=$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['attributes']['path'])" <<<"$out" 2>/dev/null) || {
        # already exists — find it
        id=$(curl -sS "${AUTH[@]}" "$API/?meta=" |
             python3 -c "import json,sys; d=json.load(sys.stdin); print(next(f['attributes']['path'] for f in d['data'] if f['attributes']['name']=='$name'))")
    }
    echo "$id"
}

# upload <local-file> <folder-path-id> <remote-name>; appends {name, id} to $MAP
upload() {
    local f=$1 folder=$2 name=$3 out id
    out=$(curl -sS "${AUTH[@]}" -X PUT --upload-file "$f" \
          "https://files.osf.io/v1/resources/$PROJECT/providers/osfstorage${folder}?kind=file&name=$name")
    id=$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['attributes']['path'].strip('/'))" <<<"$out") || {
        echo "upload failed for $name: $out" >&2; return 1; }
    python3 - "$MAP" "$name" "$id" <<'EOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1]); d = json.loads(p.read_text()) if p.exists() else {}
d[sys.argv[2]] = sys.argv[3]
p.write_text(json.dumps(d, indent=2) + "\n")
EOF
    echo "  uploaded $name -> $id"
}

INPUTS_DIR=$(mkfolder qsmci-inputs)
RAW_DIR=$(mkfolder raw)

echo "== packed QSM-CI inputs (one prepacked zip per acquisition) -> qsmci-inputs/"
for acq in data/harmonization/*/; do
    id=$(basename "$acq")
    [ "$id" = "_align" ] && continue
    z="$TMP/$id.zip"
    (cd "$acq" && zip -q -r "$z" inputs)
    upload "$z" "$INPUTS_DIR" "$id.zip"
    rm -f "$z"
done

echo "== raw acquisitions (corrected sidecars) -> raw/"
RAW=data/2026_08_20_bays_4_5_qsm_harmonization
for scanner in prisma cima; do
    for proto in bridge local pulseq_online pulseq_offline; do
        [ -d "$RAW/$scanner/$proto" ] || continue
        z="$TMP/$scanner-$proto.zip"
        (cd "$RAW/$scanner" && zip -q -r "$z" "$proto")
        upload "$z" "$RAW_DIR" "$scanner-$proto.zip"
        rm -f "$z"
    done
done
for doc in "$RAW"/README.md "$RAW"/protocols.json "$RAW"/prisma/*.pdf "$RAW"/cima/*.pdf; do
    upload "$doc" "$RAW_DIR" "$(basename "$doc")"
done

echo "done — files listed in $MAP; project: https://osf.io/$PROJECT/"
