#!/bin/bash
#SBATCH --job-name=qsmci-repro-sif
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --time=06:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=/scratch/user/uqaste15/qsmci-repro/slurm-%x-%A_%a.out

# Build compact .sif images (one inode each, ~compressed size) via apptainer --fakeroot for every
# composed-matrix method whose image can't be converted on the fly on Bunya (mksquashfs-under-proot
# ptrace failure). Sandboxes are ruled out here — the MATLAB runtimes are ~285k inodes EACH and blow
# the 1M-inode quota; a .sif is a single file. Output goes to the Bollmann project space (1 TB, huge
# inode headroom). The runner ($QSMCI_SANDBOX_DIR → prefers <name>.sif) execs these. Idempotent.
source ~/venvs/qsmci/bin/activate
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-.}"
# One image per array task: every image an active (non-ci_skip) algorithm.yml pins. LIST=1 prints
# that list (run it directly, not via sbatch) so the array can be sized to it:
#   N=$(LIST=1 bash scripts/repro_slurm/build_sifs.slurm | wc -l)
#   sbatch --array=0-$((N-1))%2 scripts/repro_slurm/build_sifs.slurm
# Keep the throttle at %2: each MATLAB runtime unpacks ~285k files into APPTAINER_TMPDIR, and 8 at
# once exceeded S0169's inode quota ("disk quota exceeded"; 8 of 54 failed on 2026-11-07).
# Each task has its own apptainer cache: concurrent builds sharing one cache corrupt it.
mapfile -t IMAGES < <(python - <<'PY'
import pathlib, yaml
seen = []
for spec in sorted(pathlib.Path("algorithms").glob("*/algorithm.yml")):
    doc = yaml.safe_load(spec.read_text()) or {}
    if doc.get("ci_skip") or not doc.get("image") or doc["image"] in seen:
        continue
    seen.append(doc["image"])
print("\n".join(seen))
PY
)
if [ "${LIST:-0}" = 1 ]; then printf '%s\n' "${IMAGES[@]}"; exit 0; fi
img=${IMAGES[${SLURM_ARRAY_TASK_ID:?submit as an array, see above}]}
export APPTAINER_CACHEDIR=/scratch/project_mnt/S0169/qsmci_apptainer_cache/$SLURM_ARRAY_TASK_ID
export APPTAINER_TMPDIR=/scratch/project_mnt/S0169/qsmci_apptainer_tmp
SIF=/scratch/project_mnt/S0169/qsmci_sif
mkdir -p "$SIF" "$APPTAINER_CACHEDIR" "$APPTAINER_TMPDIR"

ok=0; fail=0
for img in "$img"; do
  name=$(echo "$img" | sed 's#[^A-Za-z0-9._-]#_#g')   # mirrors qsm_ci.containers._sandbox_name
  dest="$SIF/$name.sif"
  if [ -f "$dest" ]; then echo "== skip (exists) $name.sif"; ok=$((ok+1)); continue; fi
  echo "== fakeroot build: $img -> $name.sif"
  if apptainer build --fakeroot "$dest.tmp" "docker://$img"; then
    mv "$dest.tmp" "$dest"; ok=$((ok+1)); echo "   OK $name.sif ($(du -h "$dest" | cut -f1))"
  else
    rm -f "$dest.tmp"; fail=$((fail+1)); echo "   FAIL $name"
  fi
done
rm -rf "$APPTAINER_CACHEDIR"
echo "sif: $ok ok, $fail failed, in $SIF"
exit $fail
