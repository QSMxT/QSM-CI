#!/bin/bash
#SBATCH --job-name=qsmci-repro-gpu
#SBATCH --account=a_ai_collab
#SBATCH --partition=gpu_cuda
#SBATCH --qos=gpu
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=256G
#SBATCH --array=0-91%6
#SBATCH --output=slurm-%x-%A_%a.out

# The two GPU-designed dipole methods (inr-qsm, modip; CUDA :v2 images) across the composed matrix,
# on gpu_cuda. `--campaign-part gpu` keeps the campaign's gpu dipoles and only the upstreams their
# `compose:` names, so each of those localfields is computed once and inverted by inr-qsm and modip on
# the GPU (QSMCI_GPU=1 -> apptainer --nv). Distinct --runs-out (runs-repro-gpu-*) so it never collides
# with the CPU matrix's shard files; the post-merge globs runs-repro-*.json and picks up both.
# inr-qsm is memory-hungry (full-volume SIREN) -> QSM_CI_JOBS=2, --mem=256G.
source ~/venvs/qsmci/bin/activate
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export APPTAINER_CACHEDIR=/scratch/user/uqaste15/apptainer_cache
export APPTAINER_TMPDIR=/scratch/user/uqaste15/apptainer_tmp
export PROOT_NO_SECCOMP=1
export QSMCI_SANDBOX_DIR=/scratch/project_mnt/S0169/qsmci_sif   # prebuilt .sif (incl. inr-qsm/modip)
export QSMCI_GPU=1            # runner adds apptainer --nv so the CUDA images see the GPU
export QSM_CI_JOBS=2          # inr-qsm SIREN is memory-hungry; 2 concurrent keeps under 256G


N_SHARDS=${N_SHARDS:-4}
# REPRO_ACQS (shell glob, default *) limits the campaign to matching acquisitions, e.g.
# REPRO_ACQS='s0*' for the EMTP traveling heads; size --array to match (acquisitions x shards).
mapfile -t ACQS < <(python -c "
import fnmatch, json, os
reg = json.load(open('scripts/datasets.json'))
pat = os.environ.get('REPRO_ACQS', '*')
print('\n'.join(sorted(k for k, v in reg.items() if v.get('track') == 'repro' and fnmatch.fnmatch(k, pat))))")
ACQ=${ACQS[$((SLURM_ARRAY_TASK_ID / N_SHARDS))]}
SHARD=$((SLURM_ARRAY_TASK_ID % N_SHARDS))

echo "== [gpu] $ACQ shard $SHARD/$N_SHARDS on $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)"
python scripts/pipeline.py \
    --phantom "$ACQ" --track repro --mode composed --runner apptainer \
    --shard "$SHARD/$N_SHARDS" \
    --campaign "${CAMPAIGN:-scripts/repro_campaign.yml}" --campaign-part gpu \
    --work ".work-repro-gpu-$ACQ-$SHARD" \
    --runs-out "results/${RUNS_PREFIX:-runs-repro-gpu}-$ACQ-s$SHARD.json"
[ "${STREAM_PUBLISH:-0}" = 1 ] && bash scripts/repro_slurm/stream_publish.sh "results/${RUNS_PREFIX:-runs-repro-gpu}-$ACQ-s$SHARD.json"
rm -rf ".work-repro-gpu-$ACQ-$SHARD"
