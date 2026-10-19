#!/bin/bash
#SBATCH --job-name=qsmci-repro-matrix-sb
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=16
# 64G, not the 300G this used to reserve: across 184 completed tasks of this exact array (same
# --exclude, same QSM_CI_JOBS) sacct put median MaxRSS at 21.7G and the PEAK at 31.4G, so 300G
# over-reserved by ~10x. 64G keeps 2x headroom over that peak. If you ever drop the inr-qsm/modip
# exclusion below, raise this again — inr-qsm's full-volume SIREN is what made the old number look
# necessary (see matrix_gpu.slurm, which keeps 256G for exactly that reason).
#SBATCH --mem=64G
# %40, not %12: the throttle was the only thing limiting concurrency here. Pending tasks sat on
# reason=JobArrayTaskLimit while the partition had thousands of idle CPUs, and 40 concurrent tasks
# schedule without trouble. At a ~1.5h median task this is ~3-4h for the 92-task array instead of
# ~12-14h.
#SBATCH --array=0-91%40
#SBATCH --output=slurm-%x-%A_%a.out

# Full-coverage re-run of the composed matrix with the local-sandbox override enabled
# (QSMCI_SANDBOX_DIR). The methods whose images couldn't be built as .sif on Bunya
# (build_sandboxes.slurm) now exec their prebuilt sandbox directories, so the ~18 DL/MATLAB/span
# methods that 100%-DNF'd in the first pass now run. Regenerates every run id; the merge upserts,
# so this supersedes the partial first pass. inr-qsm/modip stay excluded (CPU-infeasible at this
# scale — a separate GPU concern, not a container-conversion one).
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt   # before set -u (conda gotcha)
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export APPTAINER_CACHEDIR=/scratch/user/uqaste15/apptainer_cache
export APPTAINER_TMPDIR=/scratch/user/uqaste15/apptainer_tmp
export PROOT_NO_SECCOMP=1
export QSMCI_SANDBOX_DIR=/scratch/project_mnt/S0169/qsmci_sif   # runner execs the prebuilt .sif here
export QSM_CI_JOBS=4

N_SHARDS=${N_SHARDS:-4}
# RUNS_PREFIX names the shard files (pipeline.py empties its --runs-out file on start, so a campaign
# that must not overwrite earlier shard files uses its own prefix, e.g. runs-repro-v10). EXTRA_EXCLUDE
# adds slugs to --exclude (comma-separated). INCLUDE (comma-separated slugs) restricts the run to those
# stages, e.g. the upstreams plus one newly added dipole; N_SHARDS sets shards per acquisition.
# Export these in the environment and submit with --export=ALL: sbatch --export=ALL,INCLUDE=a,b
# splits on the commas and passes only INCLUDE=a.
# REPRO_ACQS (shell glob, default *) limits the campaign to matching acquisitions, e.g.
# REPRO_ACQS='s0*' for the EMTP traveling heads; size --array to match (acquisitions x shards).
mapfile -t ACQS < <(python -c "
import fnmatch, json, os
reg = json.load(open('scripts/datasets.json'))
pat = os.environ.get('REPRO_ACQS', '*')
print('\n'.join(sorted(k for k, v in reg.items() if v.get('track') == 'repro' and fnmatch.fnmatch(k, pat))))")
ACQ=${ACQS[$((SLURM_ARRAY_TASK_ID / N_SHARDS))]}
SHARD=$((SLURM_ARRAY_TASK_ID % N_SHARDS))

echo "== [sandbox] acquisition $ACQ shard $SHARD/$N_SHARDS (QSMCI_SANDBOX_DIR=$QSMCI_SANDBOX_DIR)"
python scripts/pipeline.py \
    --phantom "$ACQ" --track repro --mode composed --runner apptainer \
    --shard "$SHARD/$N_SHARDS" \
    --exclude "inr-qsm,modip${EXTRA_EXCLUDE:+,$EXTRA_EXCLUDE}" \
    ${INCLUDE:+--include "$INCLUDE"} \
    --work ".work-repro-sb-$ACQ-$SHARD" \
    --runs-out "results/${RUNS_PREFIX:-runs-repro}-$ACQ-s$SHARD.json"
[ "${STREAM_PUBLISH:-0}" = 1 ] && bash scripts/repro_slurm/stream_publish.sh "results/${RUNS_PREFIX:-runs-repro}-$ACQ-s$SHARD.json"
rm -rf ".work-repro-sb-$ACQ-$SHARD"
