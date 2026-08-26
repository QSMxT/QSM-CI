#!/bin/bash
#SBATCH --job-name=qsmci-repro-sandbox
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --time=12:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slurm-%x-%j.out

# Build apptainer SANDBOXES (image unpacked to a directory, no squashfs) for the composed-matrix
# methods whose images can't be converted to .sif on Bunya — the unprivileged apptainer's
# mksquashfs step runs under proot and the kernel blocks its ptrace ("Operation not permitted").
# A sandbox skips squashfs entirely. The runner ($QSMCI_SANDBOX_DIR, qsm_ci/containers.py) then
# execs these dirs instead of pulling docker://. Idempotent: existing sandboxes are skipped.
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export APPTAINER_CACHEDIR=/scratch/user/uqaste15/apptainer_cache
export APPTAINER_TMPDIR=/scratch/user/uqaste15/apptainer_tmp
export PROOT_NO_SECCOMP=1
SANDBOX_DIR=/scratch/user/uqaste15/apptainer_sandboxes
mkdir -p "$SANDBOX_DIR" "$APPTAINER_TMPDIR"

# Composed-matrix (field-mapping/bfr/dipole/span) methods whose images failed .sif conversion.
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
)

ok=0; fail=0
for img in "${IMAGES[@]}"; do
  name=$(echo "$img" | sed 's#[^A-Za-z0-9._-]#_#g')   # mirrors qsm_ci.containers._sandbox_name
  dest="$SANDBOX_DIR/$name"
  if [ -d "$dest" ]; then echo "== skip (exists) $name"; ok=$((ok+1)); continue; fi
  echo "== building sandbox: $img -> $name"
  if apptainer build --sandbox "$dest.tmp" "docker://$img"; then
    mv "$dest.tmp" "$dest"; ok=$((ok+1)); echo "   OK $name"
  else
    rm -rf "$dest.tmp"; fail=$((fail+1)); echo "   FAIL $name"
  fi
done
echo "sandboxes: $ok ok, $fail failed, in $SANDBOX_DIR"
ls -d "$SANDBOX_DIR"/*/ 2>/dev/null | wc -l
