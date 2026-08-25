#!/bin/bash
#SBATCH --job-name=qsmci-repro-sandbox-gpu
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slurm-%x-%j.out

# Build sandboxes for the two CUDA (GPU) dipole images (inr-qsm, modip). Building needs no GPU —
# it's just OCI extraction — so this runs on the general partition; the RUN (matrix_gpu.slurm)
# needs gpu_cuda. Idempotent.
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export APPTAINER_CACHEDIR=/scratch/user/uqaste15/apptainer_cache
export APPTAINER_TMPDIR=/scratch/user/uqaste15/apptainer_tmp
export PROOT_NO_SECCOMP=1
SB=/scratch/user/uqaste15/apptainer_sandboxes
mkdir -p "$SB" "$APPTAINER_TMPDIR"
for img in ghcr.io/astewartau/qsm-ci/inr-qsm:v2 ghcr.io/astewartau/qsm-ci/modip:v2; do
  name=$(echo "$img" | sed 's#[^A-Za-z0-9._-]#_#g')
  dest="$SB/$name"
  if [ -d "$dest" ]; then echo "skip (exists) $name"; continue; fi
  echo "building $name"
  if apptainer build --sandbox "$dest.tmp" "docker://$img"; then
    mv "$dest.tmp" "$dest"; echo "OK $name"
  else
    rm -rf "$dest.tmp"; echo "FAIL $name"
  fi
done
ls -d "$SB"/*inr-qsm* "$SB"/*modip* 2>/dev/null
