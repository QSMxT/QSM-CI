#!/bin/bash
#SBATCH --job-name=qsmci-repro-sif
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --time=12:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=/scratch/user/uqaste15/qsmci-repro/slurm-%x-%j.out

# Build compact .sif images (one inode each, ~compressed size) via apptainer --fakeroot for every
# composed-matrix method whose image can't be converted on the fly on Bunya (mksquashfs-under-proot
# ptrace failure). Sandboxes are ruled out here — the MATLAB runtimes are ~285k inodes EACH and blow
# the 1M-inode quota; a .sif is a single file. Output goes to the Bollmann project space (1 TB, huge
# inode headroom). The runner ($QSMCI_SANDBOX_DIR → prefers <name>.sif) execs these. Idempotent.
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export APPTAINER_CACHEDIR=/scratch/project_mnt/S0169/qsmci_apptainer_cache
export APPTAINER_TMPDIR=/scratch/project_mnt/S0169/qsmci_apptainer_tmp
SIF=/scratch/project_mnt/S0169/qsmci_sif
mkdir -p "$SIF" "$APPTAINER_CACHEDIR" "$APPTAINER_TMPDIR"

IMAGES=(
  ghcr.io/astewartau/qsm-ci/amp-pe:v2
  ghcr.io/astewartau/qsm-ci/autoqsm:v1
  ghcr.io/astewartau/qsm-ci/matlab-sti-ilsqr:v1
  ghcr.io/astewartau/qsm-ci/iqfm:v1
  ghcr.io/astewartau/qsm-ci/iqsm-plus:v1
  ghcr.io/astewartau/qsm-ci/iqsm:v1
  ghcr.io/astewartau/qsm-ci/ir2qsm:v1
  ghcr.io/astewartau/qsm-ci/lpcnn:v1
  ghcr.io/astewartau/qsm-ci/matlab-medi:v2
  ghcr.io/astewartau/qsm-ci/modl-qsm:v1
  ghcr.io/astewartau/qsm-ci/msmv:v1
  ghcr.io/astewartau/qsm-ci/nextqsm:v1
  ghcr.io/astewartau/qsm-ci/qsmgan:v1
  ghcr.io/astewartau/qsm-ci/qsmnet-plus:v1
  ghcr.io/astewartau/qsm-ci/qsmnet:v1
  ghcr.io/astewartau/qsm-ci/matlab-sti-star:v1
  ghcr.io/astewartau/qsm-ci/matlab-tkd:v1
  ghcr.io/astewartau/qsm-ci/xqsm:v1
  ghcr.io/astewartau/qsm-ci/inr-qsm:v2
  ghcr.io/astewartau/qsm-ci/modip:v2
)

ok=0; fail=0
for img in "${IMAGES[@]}"; do
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
echo "sif: $ok ok, $fail failed, in $SIF"
ls -la "$SIF"/*.sif 2>/dev/null | wc -l
