# Benchmark datasets — maintainer notes

The **public** description of each dataset (what it is, why a synthetic ground truth, what QSM-CI
scores and what it leaves out, how to reproduce the phantom, citations) lives on the results page,
as a per-dataset **Info** tab:

- in silico — <https://qsmxt.github.io/QSM-CI/results.html?dataset=sim&tab=info>
- χ-separation — <https://qsmxt.github.io/QSM-CI/results.html?dataset=chisep>
- in vivo — <https://qsmxt.github.io/QSM-CI/results.html?dataset=invivo>

This file holds only what that page deliberately doesn't: the mechanics of how datasets are laid
out, fetched and rebuilt. For what a *submission* sees at run time, see
[`CONTRACT.md`](../CONTRACT.md).

## Layout

Every dataset is one directory with two halves (see [`../stages.yml`](../stages.yml)):

```
<dataset>/inputs/        the public entry boundary — what a submission is given
<dataset>/groundtruth/   scoring targets, AND the boundaries mounted as isolated-mode inputs
                         (a `dipole` submission is fed the true localfield, etc.)
```

`groundtruth/` is **never committed to this repo** (the OSF zip is the source; submissions never
receive `OSF_TOKEN`, so a container cannot fetch it at run time). It is not secret, though: the
results viewer shows the truth beside every reconstruction, and each phantom's truth is published
once to the Hugging Face volumes repo as `truth/<phantom>/<artifact>.nii.gz`.

## The registry

[`scripts/datasets.json`](../scripts/datasets.json) is the source of truth — 101 entries: one `sim`,
one `invivo`, seven `chisep` phantoms (three active), and the 95 `repro` (harmonization) acquisitions. Every entry
carries:

- `track` — `sim`, `invivo`, `chisep` or `repro` — and `label`, the name the site shows.
- `path` — where `fetch_dataset.sh` unpacks it (`data/<name>/scoring`; `data/harmonization/<acq>`
  for the repro track).
- Where its zip lives on OSF: a literal `osf_file` id and/or an `osf_env` naming the CI secret that
  carries it (e.g. `OSF_FILE_CHISEP_MC`). An entry outside the default project `y8adf` adds
  `osf_project`; the harmonization entries live in the public project `gkemr` and are flagged
  `osf_public: true`, which lets `fetch_dataset.sh` download them without a token.
- `active` — whether CI scores it — and `default`, the track's primary phantom (runs on any other
  phantom get a `-<phantom>` suffix on their id). Exactly one active default per track, enforced by
  `tests/test_datasets.py`.
- `generator` (χ-separation entries built from a qsm-forward preset) — `{"tool": "qsm-forward", "ref":
  <commit>, "preset": <name>, …}`: the pinned qsm-forward commit and preset
  [`scripts/gen_chisep_preset.py`](../scripts/gen_chisep_preset.py) regenerates the zip from. Any
  other key (`r2prime_source`, `degrade_levels`) overrides that preset field; `wm_rois: true` means
  the dataset ships `groundtruth/wm_rois.nii.gz`. All generators share one ref, enforced by
  `tests/test_gen_chisep_preset.py`.
- `input_levels` (χ-separation entries) — the degraded input levels the zip ships beside its
  ground-truth inputs, e.g. `["l3"]` for `inputs-l3/` (see [χ-separation](#χ-separation)).
  `score_plan.py` plans a separate isolated `-l3` scoring job per χ-separation method on each such
  phantom; it must match the generator's `degrade_levels`, enforced by `tests/test_chisep_l3_inputs.py`.
- `prepacked: true` when the zip already holds `inputs/` (+ `groundtruth/`) at its root. Every
  entry except `sim` is prepacked.
- `group` (repro entries only) — the harmonization cohort: `harmonization` for the 72 EMTP
  traveling-head acquisitions, `harmonization-pilot` for the 23 MGH pilot acquisitions. Each cohort
  is analysed on its own and is its own dataset on the site, with its own payloads
  (`results/repro*.json` for the traveling heads, `results/repro_pilot*.json` for the pilot); the
  cohorts are defined in `REPRO_GROUPS` in [`scripts/repro_format.py`](../scripts/repro_format.py).

[`scripts/gen_manifest.py`](../scripts/gen_manifest.py) embeds the whole registry into
`web/algorithms.json` as its `datasets` block; that is how the site labels and filters runs by
phantom. It also writes the harmonization cohorts there as `repro_groups`, which the site builds its
Harmonization datasets from.

```bash
scripts/fetch_dataset.sh <registry-key> <dest>     # OSF_TOKEN required unless the entry is osf_public
```

Two shapes of zip:

- **BIDS tree** — a `qsm-forward` output (only `sim` today); `fetch_dataset.sh` finds the BIDS root
  and flattens it with [`scripts/pack_dataset.py`](../scripts/pack_dataset.py). An entry may add
  `pack_flags` (extra `pack_dataset.py` arguments such as `--chisep`); `fetch_dataset.sh` honours
  the key, but no current entry sets it — the χ-separation phantoms ship prepacked.
- **`prepacked: true`** — already flattened at the zip root, so it just unzips.

`OSF_ZIP=<path>` reuses an existing download instead of re-fetching; CI points its cache there.

## In silico (`sim`)

Scored on the QSM Challenge 2.0 realistic head model: 7 T, 4 echoes, 1 mm, 164×205×205. Sourced from
OSF project [`y8adf`](https://osf.io/y8adf/) ("QSM Rust Test Data") as a single `bids.zip` carrying
raw data plus `derivatives/qsm-forward` ground truth.

`data/sim/dev/` is a small cylinder phantom for local development, generated on demand. It validates
**plumbing only** — `totalfield == localfield`, so BFR has nothing to remove, and `dseg` is {0,1}, so
region metrics are degenerate. Don't read anything into its scores.

`dseg` label set (mirrored in `DSEG_LABELS`, [`eval/qsm_eval.py`](../eval/qsm_eval.py)):
1–6 DGM nuclei (caudate, globus pallidus, putamen, red nucleus, dentate, substantia nigra),
7 thalamus, 8 WM, 9 GM, 10 CSF, 11 blood, 13 bone, 14 air, 15 muscle, 16 calcification. (12 is unused.)

## χ-separation

Ranked (`active: true`), all regenerated from qsm-forward presets at one pinned commit by
[`scripts/gen_chisep_preset.py`](../scripts/gen_chisep_preset.py) (QSM-CI holds no generation logic
for them; it calls qsm-forward and packs):

| key | preset | what it is |
|---|---|---|
| `meso-3t` (default) | `meso-3t` | realistic 3 T: mesoscopic sub-voxel sources (hollow-cylinder myelin, iron spheres; diffusion Monte Carlo look-up tables), Chen et al. 2021's 16-echo protocol (2.7–46.2 ms), matched spin echo, 1 mm, peak SNR 100 |
| `wm-micro-7t` | `wm-micro-7t` | realistic 7 T: the same signal model, 8 echoes 3–45 ms, matched spin echo, 1 mm, peak SNR 100 |
| `ridani-3t-aniso-fitted` | `ridani-3t-aniso`, `r2prime_source: fitted` | the published reference (Ridani et al. 2026; noiseless, GRE-only, native 0.64 mm), with R2′ fitted from the simulated signal and the 3 T R2 fix |

For each method they ship R2′ fitted from the noiseless GRE and spin-echo signals
(`inputs/r2prime.nii.gz`); the imposed R2′ is `groundtruth/r2prime-formula.nii.gz`. The mesoscopic
presets read look-up tables from `$QSM_FORWARD_MESO_LUT_DIR` (see qsm-forward's README).

Retired (`active: false`; their results stay reproducible from their zips): `chisep-mc`,
`ridani-3t-iso`, `ridani-3t-aniso` and `ridani-7t-aniso`, generated by
[`scripts/gen_chisep.py`](../scripts/gen_chisep.py) — see its docstring for the exact shipping
invocation. Their R2′ uses source- and orientation-dependent relaxivities,
`R2' = Dr₊·|χ+| + Dr₋(θ)·|χ−|`; `--dr-model fixed` anchors **Dr₊ = 137 Hz/ppm** (Shin et al. 2021).

### Realistic inputs (L3)

The three ranked phantoms also ship **realistic inputs**: qsm-forward's controlled-degradation level
L3 (`qsm_forward.degrade`, generator `degrade_levels: ["L3"]`). L3 is the ground truth with the error
traits of real QSM pipelines added term by term: field-fit noise from the dataset's SNR (and the same
noise through the inversion into χ), the sub-voxel frequency and low-|k| loss of background removal,
magic-cone attenuation, low-|k| loss and smoothing of dipole inversion, residual smooth backgrounds,
a boundary error, a mean reference over a 2 mm-eroded mask, and R2′ fitted from the noisy GRE and
spin-echo signal. Each parameter is the median over six real QSMxT pipelines (iLSQR, TKD, NLTV, MEDI,
TFI, iR2QSM) run on `meso-3t`; validated downstream, χ-separation methods fed L3 rank as they do when
fed real pipeline outputs (Spearman ρ 0.92 on `meso-3t`, 0.89 on `wm-micro-7t`), about 0.02 XSIM
optimistic. The ground-truth inputs stay as they were and are the upper bound.

```
inputs-l3/   localfield  chimap  chimap-echoes  r2prime  mask   (.nii.gz, canonical names)
groundtruth/degradation-l3.json   every parameter, the seed, the qsm-forward version, the calibration spread
```

`pipeline.py --inputs l3` mounts those five artifacts in place of the ground-truth ones (the raw
signal, params and dseg are shared), scores against the same ground truth over the same brain mask
(`inputs/mask.nii.gz`), and writes rows with `-l3` ids and `inputs: "l3"`. L3 always ships
`chimap-echoes` (per-echo χ, each echo with its own phase noise), so DECOMPOSE gets a per-echo input
at L3 while it falls back to `chimap` on the ground-truth inputs. `ridani-3t-aniso-fitted` is noiseless
and GRE-only, so its L3 has the transfer and additive terms but no noise, and its R2′ is the shipped
one; the calibration was validated on the two mesoscopic phantoms only.

Every χ-separation phantom carries `groundtruth/wm_rois.nii.gz` (`--wm-rois-src` for both
generators; omitting it still scores, but silently drops the per-ROI MSPE).

When qsm-forward writes the echo-dependent χ(TE) (`*_Chimap-echoes.nii`), `pack_dataset.py` ships it
as `inputs/chimap-echoes.nii.gz` (x,y,z,echo, ppm, masked to the brain like `chimap`). It is the
optional per-echo QSM input DECOMPOSE takes ([`CONTRACT.md`](../CONTRACT.md)). None of the
ranked phantoms carries it, so their DECOMPOSE runs fall back to `chimap` at every echo.

A phantom packed from a qsm-forward chi-sep BIDS tree (`qsm-forward chi-sep --preset …`) also
carries what that tree records about the phantom:

- `inputs/r2prime.nii.gz` is qsm-forward's `*_R2prime`, the R2′ methods are given. With
  `r2prime_source=fitted` it is fitted from the simulated GRE and spin-echo signal.
- `groundtruth/r2prime-formula.nii.gz` is `*_desc-formula_R2prime`, the R2′ the phantom imposes
  (Dr+·|χ+| + Dr−·|χ−|). It is a reference beside the ground truth and is never mounted into a
  method.
- `groundtruth/chisep.json` is `*_chisep.json`, the phantom's configuration and relaxivity.
- `inputs/params.json` gains `chisep_dr_hz_per_ppm`, the imposed Dr+ (`Relaxivity.Dr` for a
  co-located phantom, `Relaxivity.DrPos` for the Ridani model). It is for documentation and for
  matching a phantom to a method's assumptions when reading scores. No method reads it; each keeps
  its published default.
- `inputs/r2.nii.gz`, `groundtruth/theta.nii.gz` and `groundtruth/wm_rois.nii.gz` come from
  `*_R2map`, `*_fibreangle` and `*_desc-wmrois_dseg` when the tree has them.

## In vivo (`invivo`)

2016 QSM Reconstruction Challenge data. Ships **prepacked**, built by
[`scripts/make_invivo_zip.py`](../scripts/make_invivo_zip.py) from the challenge release NIfTIs
(`phs_tissue` → `localfield`, `chi_cosmos` → `chimap`, `chi_33` → `chimap-sti`), with a unit sanity
check that everything is ppm-scale.

Only the `dipole` stage is scorable — the dataset ships the local tissue field and the two χ
references, and no field-mapping or BFR ground truth, so this track is isolated-only with no composed
matrix. Each method is scored against both references in one recon: COSMOS takes the unsuffixed
metric keys, STI χ33 the `_sti` ones (the CSV export renames these to `_cosmos` / `_chi33`).

The shipped `dseg.nii.gz` uses the challenge's own 0–11 label scheme, **not** the sim phantom's, so
it is not used for scoring.

## Harmonization (`repro`, 95 acquisitions in two cohorts)

The no-ground-truth reproducibility track, in two independent cohorts (registry `group`):

- **EMTP traveling heads** (`group: harmonization`, 72 acquisitions): six subjects, each scanned at
  their home site (KKI Philips) and, for four of them, at one or two further sites (Weill Cornell
  CBIC GE/Siemens, UMass Siemens, Hamburg Philips), with the bridge and local protocols, three runs
  each. Registry keys are `<subject>-<scanner>-<protocol>-run<n>` (scanner tags such as
  `kki-achieva`, `cbic-mr750`). Packed by [`scripts/pack_emtp.py`](../scripts/pack_emtp.py).
- **MGH pilot** (`group: harmonization-pilot`, 23 acquisitions): one subject on two Siemens 3 T
  scanners (`prisma` = MAGNETOM Prisma Fit, `cima` = MAGNETOM Cima.X) with four protocols (`bridge`,
  `local`, `pulseq-online`, `pulseq-offline`), three runs each (one Pulseq offline run could not be
  reconstructed). Registry keys are `<scanner>-<protocol>-run<n>`.

All are `default: false`, prepacked, in the public OSF project `gkemr`
([`scripts/osf_harmonization_files.json`](../scripts/osf_harmonization_files.json) records each
upload's file id).

The MGH pilot was packed from the raw MGH export by
[`scripts/pack_harmonization.py`](../scripts/pack_harmonization.py) — which recovers the echo times
the sidecars lack from the exam-card PDFs and the Pulseq sequence definition — and uploaded by
[`scripts/publish_harmonization_osf.sh`](../scripts/publish_harmonization_osf.sh). Each zip holds
`inputs/` only: there is no `groundtruth/`. Scoring is cross-acquisition agreement per pipeline,
computed by [`scripts/repro_eval.py`](../scripts/repro_eval.py) (register → stats → fits) into one
payload per cohort (`results/repro.json` for the traveling heads, `results/repro_pilot.json` for the
MGH pilot, each with its fit columns); the Bunya job sequence that runs the full matrix is documented in
[`scripts/repro_slurm/README.md`](../scripts/repro_slurm/README.md).
