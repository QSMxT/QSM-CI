# Harmonization (repro track) — full matrix on Bunya

Runs every QSM-CI pipeline combination over all 95 harmonization acquisitions
(`data/harmonization/*`: the 72 EMTP traveling-head and 23 MGH pilot acquisitions), then the
reproducibility evaluation (register → SynthSeg → ROI stats → ax+b fits, per cohort), entirely on
Bunya. Only the small JSON payloads come back; the ~10k recon volumes stay
in scratch.

## What publishes what

Three kinds of harmonization volume belong to no single run and are addressed by NAMING CONVENTION,
not by any URL in `index.json` — the viewer rebuilds their URLs from the pattern. They therefore have
their own publishers. `publish_volumes.py --prune` (the per-run, URL-based prune) deliberately does
not judge them; `--prune-repro` (repro.yml's evaluate job) does, by rebuilding the same pattern from
each cohort's live pipelines (`repro.json`, `repro_pilot.json`) × that cohort's acquisitions in
`scripts/datasets.json` and deleting what falls
outside it AND names a method `web/algorithms.json` no longer defines — a retired method's recons
and the columns only it used. Files of live methods that merely lack ROI stats (unharvested GPU
runs, parked submissions) are kept:

| file | published by |
|---|---|
| `repro/<acq>/<acq>__magnitude.nii.gz` | `mag_rss_upload.py` |
| `repro/<acq>/<fm>__totalfield.nii.gz` | `publish_repro_intermediates.py` (`publish_intermediates.slurm`) |
| `repro/<acq>/<fm>_<bfr>__localfield.nii.gz` | same |

If you add a fourth such kind, add it to that list and check `publish_volumes.RUN_ARTIFACTS` still
excludes it — a 2026-09 dry run found prune ready to delete all 621 of these as "orphans".

## Everything runs through sbatch

Bunya's login node is shared, so anything that lists a 57k-file repo, uploads gigabytes, or takes
more than a few seconds belongs in a batch job — including the "just a dry run" ones, which still
publish in full because `--prune-dry-run` suppresses deletion only. Every job here is an sbatch
script for that reason; the login node is for `squeue`, `sacct`, `sbatch` and reading logs.

## Collapsing the ground-truth copies (2026-09, done once)

The Hub accumulated per-run copies of each phantom's ground truth, plus the volumes of runs since
renamed or retired. Clearing it is a five-step sequence, and the ORDER is what keeps the site
working — an index that still points at a file must be repointed and DEPLOYED before that file goes:

| step | job | what |
|---|---|---|
| 1 | `flat_run.slurm` | `--prune --prune-flat`: volumes of retired runs |
| 2 | `dedupe_repoint.slurm` | upload shared truth, repoint the DEPLOYED index → commit + deploy |
| 3 | `dedupe_repoint_hpc.slurm` | repoint the HPC index (releases what it protected) |
| 4 | `dedupe_delete.slurm` | `--delete-legacy`: the per-run copies |
| 5 | `squash.slurm` | reclaim the LFS objects (Hub quota lags ~36h) |

`*_dry.slurm` are the dry-run counterparts. Run them and READ THEM: step 1's dry run is what caught
`--prune` proposing to delete 621 live shared intermediates, and a dry run of the old dedupe found it
about to delete 165 volumes the site was serving. A file both indexes reference needs BOTH repointed
before it can go, which is why steps 2 and 3 are separate.

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
# Bunya's miniconda (conda 4.7) can no longer solve new envs: the jobs use a venv on the system
# Python 3.9 instead (QSM-CI needs >= 3.9).
[ -x ~/venvs/qsmci/bin/python ] || /usr/bin/python3.9 -m venv ~/venvs/qsmci
source ~/venvs/qsmci/bin/activate
SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 pip install -e .                # qsm-ci CLI (no .git after rsync)
pip install SimpleITK matplotlib                                     # repro_eval register/stats, figures
# Bunya's apptainer can't convert OCI images on the fly (mksquashfs under proot), so every image is
# prebuilt as a fakeroot .sif in /scratch/project_mnt/S0169/qsmci_sif (QSMCI_SANDBOX_DIR), one array
# task per image; existing .sifs are skipped. MUST finish before the matrix.
N=$(LIST=1 bash scripts/repro_slurm/build_sifs.slurm | wc -l)
sbatch --array=0-$((N-1))%2 scripts/repro_slurm/build_sifs.slurm   # %2: MATLAB unpacks hit the inode quota
```

## The streamed campaign (v11 onward)

What runs is `scripts/repro_campaign.yml`: the QSM.rs ports (an original with a parity-checked port
is left out), the originals with no port, the ports' parity versions, and the authors' own chains. The
full matrix's volumes don't fit in scratch, so every shard computes its ROI stats, uploads its
reconstructions to the Hub and deletes them as it ends (`stream_publish.sh`), and 16 shards per
acquisition keep each task to ~60 pipelines.

```bash
N=$(python -c "import json; print(sum(v.get('track') == 'repro' for v in json.load(open('scripts/datasets.json')).values()))")
PREP=$(sbatch --parsable scripts/repro_slurm/prep.slurm)                    # transforms + SynthSeg, once
export STREAM_PUBLISH=1 RUNS_PREFIX=runs-repro-v11 N_SHARDS=16
# array indices stop at 1000 on Bunya: one array per 1000 tasks, ARRAY_OFFSET = its first task
CPU=$(sbatch --parsable --export=ALL --dependency=afterok:$PREP --array=0-999%40 \
      scripts/repro_slurm/matrix_sandbox.slurm)
CPU2=$(ARRAY_OFFSET=1000 sbatch --parsable --export=ALL --dependency=afterok:$PREP \
       --array=0-$((16*N-1001))%40 scripts/repro_slurm/matrix_sandbox.slurm)
export RUNS_PREFIX=runs-repro-v11-gpu N_SHARDS=4                           # gpu QOS: 100 jobs a user
GPU=$(sbatch --parsable --export=ALL --dependency=afterok:$PREP --time=7-00:00:00 --mem=2G \
      scripts/repro_slurm/gpu_driver.sh $N)
sbatch --export=ALL --array=0-$((N-1))%8 scripts/repro_slurm/intermediates.slurm   # viewer field maps
# after both: rows already carry their stats; FRESH_START=1 drops the previous campaign's rows
sbatch --account=a_ai_collab --partition=general --time=08:00:00 --cpus-per-task=12 --mem=64G \
  --dependency=afterany:$CPU:$CPU2:$GPU --wrap \
  "SKIP_STATS=1 FRESH_START=1 bash scripts/repro_slurm/harvest.sh 'results/runs-repro-v11*.json'"
```

## The matrix (before v11)

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
# payload: results/index.json (merged), results/repro_rois.json, per cohort results/repro.json +
#          repro_fits*.bin (traveling heads) and results/repro_pilot.json + repro_pilot_fits*.bin
#          (MGH pilot), data/harmonization/_align/ (transforms + dseg + target)
# then regenerate the regional payloads (results/repro_regions.*, results/repro_pilot_regions.*):
python scripts/gen_repro_regions.py results/repro_rois.json results
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
