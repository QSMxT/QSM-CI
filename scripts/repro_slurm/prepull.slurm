#!/bin/bash
#SBATCH --job-name=qsmci-repro-prepull
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=slurm-%x-%j.out

# Serially convert every submission image into the apptainer cache BEFORE the matrix array runs —
# concurrent array tasks racing to convert the same docker:// image corrupt the shared cache.
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt   # before set -u (conda gotcha)
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export APPTAINER_CACHEDIR=/scratch/user/uqaste15/apptainer_cache

python - <<'EOF' | sort -u > /tmp/images.$$
import re, yaml, pathlib
for spec in pathlib.Path("algorithms").glob("*/algorithm.yml"):
    doc = yaml.safe_load(spec.read_text()) or {}
    if doc.get("ci_skip") or not doc.get("image"):
        continue
    print(doc["image"])
EOF

while read -r img; do
    echo "== pre-pulling $img"
    apptainer exec "docker://$img" true
done < /tmp/images.$$
rm -f /tmp/images.$$
echo "pre-pull complete"
