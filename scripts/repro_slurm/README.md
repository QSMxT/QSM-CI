# Harmonization (repro track) — full matrix on Bunya

Runs every QSM-CI pipeline combination over all 23 harmonization acquisitions
(`data/harmonization/*`), then the reproducibility evaluation (register → SynthSeg → ROI stats →
ax+b fits), entirely on Bunya. Only the small JSON payloads come back; the ~10k recon volumes stay
in scratch.

## One-time setup

```bash
# from the local checkout (repo + packed inputs; raw data not needed on Bunya)
rsync -a --info=progress2 --exclude .work --exclude 'results/*/' \
    ./ bunya:/scratch/user/uqaste15/qsmci-repro/
ssh bunya                                                            # login node, see below
cd /scratch/user/uqaste15/qsmci-repro
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt   # BEFORE set -u (conda gotcha)
SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 pip install -e .                # qsm-ci CLI (no .git after rsync)
pip install SimpleITK                                                # for repro_eval register/stats
export APPTAINER_CACHEDIR=/scratch/user/uqaste15/apptainer_cache
sbatch scripts/repro_slurm/prepull.slurm      # serial image pre-pull — MUST finish before the array
```

## The matrix

```bash
MATRIX=$(sbatch --parsable scripts/repro_slurm/matrix.slurm)      # 23 acquisitions x 4 shards
sbatch --dependency=afterany:$MATRIX scripts/repro_slurm/post.slurm
```

`matrix.slurm` array task i runs `pipeline.py --phantom <acq> --track repro --mode composed
--runner apptainer --shard s/4 --runs-out results/runs-repro-<acq>-s<s>.json`. No ground truth is
involved: chains start at the field-mapping stage; each produced χ map is validated and archived
under `results/<run-id>/recon.nii.gz` (scratch).

`post.slurm` then: merges the per-shard run files into `results/index.json`, runs
`repro_eval.py register` (rigid, SimpleITK), SynthSeg on the target magnitude via apptainer,
`repro_eval.py stats` and `fits`, and tars the take-home payload.

## Bring the results home

```bash
scp bunya:/scratch/user/uqaste15/qsmci-repro/repro_payload.tar.gz /tmp/
tar -C /home/ashley/repos/qsm/qsmci/qsmci -xzf /tmp/repro_payload.tar.gz
# payload: results/index.json (merged), results/repro_rois.json, results/repro.json,
#          data/harmonization/_align/ (transforms + dseg + target)
```

## Tuning a running array

Both `--mem` and the concurrency throttle can be changed on an array that is already queued, without
resubmitting — the change applies to PENDING tasks; running ones keep the allocation they started
with:

```bash
scontrol update JobId=<id> MinMemoryNode=65536     # MEGABYTES — "64G" is rejected
scontrol update JobId=<id> ArrayTaskThrottle=40
```

**Set the memory before the throttle.** Raising the throttle launches the newly-allowed tasks
immediately, and they start with whatever `--mem` they already had — so doing it the other way round
leaves almost every task on the old value.

To tell whether the array is actually cluster-limited or just self-throttled, check the pending
reason: `JobArrayTaskLimit` means it is our own `%N`, not the cluster. `sinfo -p general` shows what
is genuinely free.

Sanity notes (from the sweep campaigns): batch nodes have ~1.5 TB RAM but interactive sallocs are
memory-capped — never judge OOM from a salloc; inr-qsm needs jobs≤2 at 200G (the CPU matrices use
QSM_CI_JOBS=4 at 64G, which holds because at most one DL dipole runs per combo at a time and
inr-qsm/modip are excluded — drop jobs to 2, and raise the memory, if a shard OOMs).

`--mem=64G` is measured, not guessed: 184 completed tasks of this array had a median MaxRSS of
21.7 GB and a peak of 31.4 GB (`sacct --name=qsmci-repro-matrix-sb --format=JobID,MaxRSS`). The
300 GB it used to request over-reserved by ~10x. It was NOT what limited concurrency, though — 40
tasks at 300 GB scheduled fine; the `%12` throttle was simply conservative.

## Getting a shell for monitoring

Use the **login node** (`ssh bunya`), not a compute node. `pam_slurm_adopt` grants access to a
`bunNNN` host only while you have a job running on that node, so a compute-node session dies the
moment that job ends — mid-monitoring, with `Access denied by pam_slurm_adopt: you have no active
jobs on this node`. `squeue`, `sacct`, `sbatch` and `scontrol` all work from the login node.
