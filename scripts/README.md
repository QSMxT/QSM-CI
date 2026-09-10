# scripts/

Maintainer tooling. Nothing here ships in the `qsm-ci` package (that is `qsm_ci/`); run everything
from the repo root (`python scripts/<name>.py`, `scripts/<name>.sh`). Each script's docstring is the
full reference — this file only says what each one is for and who calls it.

## CI — called by the workflows in `.github/workflows/`

| Script | What it does | Called from |
|---|---|---|
| `pipeline.py` | The evaluation runner: discovers submissions under `algorithms/`, runs the isolated + composed matrix on a dataset, scores every artifact with `qsm-eval`, writes `results/` | `score.yml`, `evaluate.yml`, `pipeline.yml`, `repro.yml` |
| `ci_eval_targets.py` | Decides which *changed* submissions need a per-PR smoke run (a code change, not a metadata-only `algorithm.yml` edit) | `evaluate.yml` |
| `gen_manifest.py` | **Reads** every `algorithms/*/algorithm.yml` (plus `datasets.json`) and writes `web/algorithms.json`, the manifest the site is built from. Not to be confused with `oneoff/gen_algorithms.py`, which *writes* submission folders | `ci.yml` (manifest sync commit) |
| `merge_index.py` | Upserts the runs a rescore changed into the latest `results/index.json` by run id, so concurrent rescores never clobber each other | `score.yml`, `repro.yml` |
| `publish_volumes.py` | Uploads per-run viewer volumes (and each phantom's truth, once) to the Hugging Face volumes repo and stamps their URLs into the index | `score.yml`, `repro.yml`, `hf-check.yml` |
| `publish_repro_intermediates.py` | Publishes the harmonization track's shared total-/local-field intermediates to the same HF repo | `repro.yml` |
| `repro_eval.py` | The no-ground-truth harmonization analysis (`register` / `stats` / `fits`) → `results/repro.json` | `repro.yml`; Bunya via `repro_slurm/` |
| `squash_hf_history.py` | Collapses the HF volumes repo's history to one commit to reclaim LFS storage (old versions and pruned paths stay in history until then). Best-effort: never fails its caller | `score.yml` merge job after every FULL rescore; `hf-housekeeping.yml` (`workflow_dispatch`) for a one-off; `repro_slurm/squash.slurm` on Bunya |
| `fetch_dataset.sh` | Downloads a registry phantom's zip from OSF and unpacks it into `inputs/` + `groundtruth/` (flattening a BIDS tree with `pack_dataset.py` when needed) | `score.yml`, `evaluate.yml`, `pipeline.yml`, `repro.yml` |
| `datasets.json` | The dataset/phantom registry — see [`data/README.md`](../data/README.md) | `fetch_dataset.sh`, `pipeline.py`, `gen_manifest.py`, the workflows |

## Dataset building and packing

How each shipped dataset was made; re-run only to rebuild one.

| Script | What it does |
|---|---|
| `pack_dataset.py` | Flattens a `qsm-forward` BIDS output into the canonical `inputs/` + `groundtruth/` layout (used by `fetch_dataset.sh` and `gen_chisep.py`) |
| `gen_chisep.py` | Reproducible generator for the χ-separation phantoms (`chisep-mc`, `ridani-*`) from the Challenge 2.0 head model; `--validate` runs `validate_phantom.py` on the result |
| `validate_phantom.py` | Measures whether a χ-separation phantom can discriminate methods (null-model triviality, noise ceiling) before spending hours on real separators |
| `make_invivo_zip.py` | Packs the 2016 QSM Challenge release into the prepacked in-vivo zip (`invivo`) |
| `pack_harmonization.py` | Packs the raw MGH two-scanner drop into the 23 prepacked harmonization acquisitions (`repro`), recovering the echo times the sidecars lack |
| `publish_harmonization_osf.sh` | Uploads those acquisitions (and the raw exports) to the public OSF project; records file ids in `osf_harmonization_files.json` |
| `osf_harmonization_files.json` | The OSF file ids of every harmonization upload |
| `mirror_ridani_osf.py` | Mirrors the Ridani et al. OSF project (9xwhz) locally, with a manifest, as the bit-for-bit reference for the Ridani phantoms |
| `verify_ridani_gt.py` | Checks the `qsm-forward`-generated Ridani ground truth against that mirror and the paper's tables |

## Parameter sweeps and tuning

| Script | What it does |
|---|---|
| `sweep.py` | Isolated-mode grid sweep of each tunable method's parameters (xSIM objective) → `results/sweep_*.json`; run on Bunya |
| `sweep_report.py` | Baseline-vs-best table over the sweep outputs |
| `combo_sweep.py` | Joint (BFR → dipole) sweep: does a dipole method's isolated-tuned value survive being chained behind a real BFR? → `results/combo_sweep.json` |
| `combo_sweep_report.py` | Per-cell isolated-vs-in-combination report for the joint sweep |
| `prune_stale_tuned.py` | Drops `tuned` runs from `results/index.json` whose declared tuned value no longer exists in the method's `algorithm.yml` (tested by `tests/test_prune_stale_tuned.py`) |

## Diagnostics

| Script | What it does |
|---|---|
| `crosscheck_qsmrs.sh` | Drift guard: scores one recon with `qsm-eval` and with QSM.rs's own `ChallengeMetrics` and checks they agree (needs a QSM.rs checkout and the `qsm-ci` CLI) |
| `check_r2prime_consistency.py` | Is a phantom's shipped R2′ ground truth consistent with its shipped GRE/SE signal? (fits R2\* − R2 and correlates) |
| `gen_repro_regions.py` | Compacts `results/repro_rois.json` into the `results/repro_regions.json` the harmonization Findings figures read; re-run after a harmonization publish |

## HPC (Bunya)

`repro_slurm/` holds the SLURM job files and helpers for running the full harmonization matrix
(CPU and GPU), building the apptainer images, and the HF publish/prune/squash sequence on Bunya. It
has its own [README](repro_slurm/README.md).

## `oneoff/` — done, kept for the record

Migrations and backfills that have already been applied to the published data, plus the scaffold
that first generated the QSM.rs submissions. They still run (each computes the repo root from its
own location), but there is no reason to run them again unless the situation they fixed recurs.

| Script | What it did |
|---|---|
| `oneoff/apply_metadata.py` | Added the taxonomy fields (`language`, `family`, `learning`, `engine`) to every `algorithm.yml` |
| `oneoff/backfill_regions.py` | Wrote per-run `regions.json` for runs scored before per-region stats existed, from their archived volumes |
| `oneoff/backfill_resources.py` | Stamped peak-memory / CPU summaries onto runs scored before `pipeline.py` recorded them |
| `oneoff/dedupe_hf_truth.py` | Collapsed the per-run ground-truth copies on the HF volumes repo into one shared file per phantom and repointed the index (the `repro_slurm/dedupe_*.slurm` jobs; tested by `tests/test_dedupe_hf_truth.py`) |
| `oneoff/gen_algorithms.py` | Generated the original `algorithms/*-qsmrs/` folders (`algorithm.yml`, `run.sh`, `README.md`). **Do not re-run**: the folders have since been hand-edited (authors, taxonomy, tuned parameters, tuning provenance) and it would overwrite them |
