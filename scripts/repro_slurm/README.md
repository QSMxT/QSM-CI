# Harmonization (repro track) — full matrix on Bunya

Runs every QSM-CI pipeline combination over all 23 harmonization acquisitions
(`data/harmonization/*`), then the reproducibility evaluation (register → SynthSeg → ROI stats →
ax+b fits), entirely on Bunya. Only the small JSON payloads come back; the ~10k recon volumes stay
in scratch.

## One-time setup

```bash
# from the local checkout (repo + packed inputs; raw data not needed on Bunya)
rsync -a --info=progress2 --exclude .work --exclude 'results/*/' \
    ./ bun143:/scratch/user/uqaste15/qsmci-repro/
ssh bun143
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
scp bun143:/scratch/user/uqaste15/qsmci-repro/repro_payload.tar.gz /tmp/
tar -C /home/ashley/repos/qsm/qsmci/qsmci -xzf /tmp/repro_payload.tar.gz
# payload: results/index.json (merged), results/repro_rois.json, results/repro.json,
#          data/harmonization/_align/ (transforms + dseg + target)
```

Sanity notes (from the sweep campaigns): batch nodes have ~1.5 TB RAM but interactive sallocs are
memory-capped — never judge OOM from a salloc; inr-qsm needs jobs≤2 at 200G (the matrix uses
QSM_CI_JOBS=4 with 300G, which holds because at most one DL dipole runs per combo at a time — drop
to 2 if a shard OOMs).
