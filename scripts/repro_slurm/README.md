# Harmonization (repro track) — full matrix on Bunya

Runs every QSM-CI pipeline combination over all 23 harmonization acquisitions
(`data/harmonization/*`), then the reproducibility evaluation (register → SynthSeg → ROI stats →
ax+b fits), entirely on Bunya. Only the small JSON payloads come back; the ~10k recon volumes stay
in scratch.

## What publishes what

Three kinds of harmonization volume belong to no single run and are addressed by NAMING CONVENTION,
not by any URL in `index.json` — the viewer rebuilds their URLs from the pattern. They therefore have
their own publishers, and `publish_volumes.py --prune` deliberately does not judge them:

| file | published by |
|---|---|
| `repro/<acq>/<acq>__magnitude.nii.gz` | `mag_rss_upload.py` |
| `repro/<acq>/<fm>__totalfield.nii.gz` | `publish_repro_intermediates.py` (`publish_intermediates.slurm`) |
| `repro/<acq>/<fm>_<bfr>__localfield.nii.gz` | same |

If you add a fourth such kind, add it to that list and check `publish_volumes.RUN_ARTIFACTS` still
excludes it — a 2026-09 dry run found prune ready to delete all 621 of these as "orphans".

## Re-sync before every campaign (this bites)

The one-time setup below rsyncs the repo to scratch, and the checkout there then **stays at whatever
revision it was rsynced at**. It is not a clone: `git pull` is not available, nothing warns you, and
the jobs happily run months-old code. Every bug in the 2026-09 recompute traces to that:

| stale file on Bunya | what it silently did |
|---|---|
| `scripts/publish_volumes.py` | predated `--prune`, so `--prune-dry-run` was filtered out as an unknown flag; the job published, pruned nothing, printed nothing and exited 0 |
| `web/algorithms.json` (3 weeks old) | `drop_retired` dropped 24 live `amp-pe-qsmrs` pipelines from `repro.json` |
| `scripts/pipeline.py` | predated `write_run_regions`, so 14,551 runs kept the previous matrix's `regions.json` next to a freshly computed recon |

So **re-run the rsync before each campaign**, and check what actually differs when a result surprises
you:

```bash
# from the local checkout — what is Bunya running?
for f in $(git ls-files scripts | grep '\.py$'); do
  b=$(ssh bunya "md5sum /scratch/user/uqaste15/qsmci-repro/$f 2>/dev/null | cut -d' ' -f1")
  [ "$b" != "$(md5sum "$f" | cut -d' ' -f1)" ] && echo "DIFFERS $f"
done
```

`web/algorithms.json` matters as much as the scripts: `repro_eval.py fits` uses it to decide which
pipelines still exist, so a stale copy silently changes the published pipeline set.

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

## Viewer intermediates (field map + local field)

The submission page can show a harmonization pipeline's upstream stages next to its reconstruction:
the field-mapping stage's **total field** and the background-removal stage's **local field**. Those
maps live in the matrix's work dirs, which `matrix*.slurm` deletes, so they are regenerated on their
own:

```bash
INTER=$(sbatch --parsable scripts/repro_slurm/intermediates.slurm)          # 23 acquisitions
sbatch --dependency=afterany:$INTER scripts/repro_slurm/publish_intermediates.slurm
```

`intermediates.slurm` runs `pipeline.py --columns-only --emit-intermediates`, which stops after the
field-mapping and background-removal stages. They are per-COLUMN, not per-pipeline — one total field
per field-mapping method, one local field per (field-mapping, bfr) pair — so this is **26 runs per
acquisition** (2 field maps + 2x12 local fields), not the 660-pipeline matrix. Each lands in
`results/_intermediates/<acq>/` under the basename it takes on the Hub:

```
<field-mapping>__totalfield.nii.gz
<field-mapping>_<bfr>__localfield.nii.gz
```

`publish_intermediates.slurm` uploads them into the same `repro/<acq>/` directory as the recons, where
`web/js/viewer.js` derives their URLs from the pipeline id. The viewer HEAD-probes each URL and shows
the tab only on a hit, so a pipeline with no such stage (a bfr+dipole span, an end-to-end method) and
an acquisition that hasn't been published yet both just show fewer tabs.

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
