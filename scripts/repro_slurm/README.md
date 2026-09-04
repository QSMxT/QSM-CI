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
scp bun143:/scratch/user/uqaste15/qsmci-repro/repro_payload.tar.gz /tmp/
tar -C /home/ashley/repos/qsm/qsmci/qsmci -xzf /tmp/repro_payload.tar.gz
# payload: results/index.json (merged), results/repro_rois.json, results/repro.json,
#          data/harmonization/_align/ (transforms + dseg + target)
```

Sanity notes (from the sweep campaigns): batch nodes have ~1.5 TB RAM but interactive sallocs are
memory-capped — never judge OOM from a salloc; inr-qsm needs jobs≤2 at 200G (the matrix uses
QSM_CI_JOBS=4 with 300G, which holds because at most one DL dipole runs per combo at a time — drop
to 2 if a shard OOMs).
