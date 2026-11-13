# Toolbox pipeline (QSMxT / QSM.rs)

A whole original toolbox's QSM pipeline, from the raw echoes to χ, as QSMxT reproduces it with
QSM.rs: `qsmxt run --pipeline <id>`. It is the candidate side of pipeline parity
([QSMxT/QSM-CI#421](https://github.com/QSMxT/QSM-CI/issues/421)): each pipeline is compared with the
toolbox's own script, run end to end by a reference submission. It is never scored against ground
truth (`parity_only`).

- **Stage:** `pipeline` (phase, magnitude, params → chimap; also chi-para, chi-dia from the
  χ-separation pipelines). No mask is given: making it is part of the pipeline, except with
  `dataset_mask`, which takes the dataset's.
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) and [QSM.rs](https://github.com/astewartau/QSM.rs)
  (`qsm_core::pipeline::reference_pipelines`).

## How QSM-CI runs it

`run.sh` turns `/input` into a one-run BIDS dataset (`sub-1/anat/sub-1_echo-<n>_part-{phase,mag}_MEGRE`,
the 4-D inputs split into one file per echo with their data bytes untouched) with a sidecar per echo:
`EchoTime`, `EchoNumber`, `MagneticFieldStrength`, `B0_dir`, and `ImagingFrequency` and
`Manufacturer` when `params.json` has them. `MagneticFieldStrength` is `params.json` `B0_nominal`
where the dataset has one (its `B0` was then computed from the centre frequency), as a scanner's
sidecar would say, else `B0`. Then:

```bash
qsmxt run bids/ out/ --pipeline <id> --output-space acquired
```

`--pipeline` sets every reconstruction setting to the toolbox's; no other setting is changed.
`--output-space acquired` (QSMxT's default) keeps the outputs on the input grid.

| Parameter | Default | |
|---|---|---|
| `pipeline` | `qsmxt-defaults` | `medi-toolbox`, `sti-suite-ilsqr`, `sti-suite-star`, `qsmart`, `heidi`, `chi-sep-ilsqr`, `chi-sep-medi`, `chi-sepnet`, `decompose`, `uk-biobank`, or `qsmxt-defaults` |
| `dataset_mask` | `false` | `true`: use the dataset's `mask.nii.gz` (`--use-custom-masks`) instead of the mask the pipeline makes, for a toolbox whose mask needs data no pipeline input has (UK Biobank's comes from its T1 pipeline) |

```bash
qsm-ci run toolbox-pipeline-qsmrs --phase phase.nii.gz --magnitude magnitude.nii.gz \
  --params params.json --set pipeline=medi-toolbox -o out/ --image <qsmxt build> --intermediates inter/
```

## Outputs

| File | From qsmxt |
|---|---|
| `chimap.nii.gz` | `sub-1_Chimap` |
| `chi-para.nii.gz`, `chi-dia.nii.gz` | `sub-1_desc-paramagnetic_Chimap`, `sub-1_desc-diamagnetic_Chimap` (χ-separation pipelines) |

Intermediates (`$QSMCI_INTERMEDIATES`, CONTRACT.md names), each written when qsmxt made it:

| Name | From qsmxt | Units |
|---|---|---|
| `mask` | `sub-1_mask` (the pipeline's brain mask) | 0/1 |
| `totalfield` | `workflow/…/unwrap/sub-1_desc-totalppm_fieldmap` | ppm |
| `localfield` | `workflow/…/bgremove/sub-1_localfield` | ppm |
| `chimap_unreferenced` | `workflow/…/invert/sub-1_desc-unreferenced_Chimap` | ppm |
| `r2star`, `r2prime` | `sub-1_R2starmap`, `sub-1_R2primemap` | Hz |
| `reliability`, `vessel_mask` | QSMART: `sub-1_desc-echofit_mask`, `sub-1_desc-vessels_mask` | 0/1 |
| `localfield_stage1/2`, `chimap_stage1/2` | QSMART: `sub-1_desc-stage{1,2}_{localfield,Chimap}` | ppm |
| `chimap_echo<n>` | `sub-1_desc-echo<n>_Chimap` (a pipeline that inverts each echo) | ppm |

The `workflow/` maps are on qsmxt's working grid. When qsmxt resampled an oblique acquisition to an
axial grid, they are not on the input grid, and `run.sh` leaves them out with a note rather than
resample them itself (a resampling of its own would be a difference neither pipeline has).

## Image

The shared qsmxt image (`algorithms/_qsmxt`), pinned to v11.0.0, which has no `--pipeline` yet: the
submission is `ci_skip` and runs against a qsmxt build, as parity's development track does. The
χ-separation pipelines estimate R2′ with R2PRIMEnet when there is no spin-echo data, and
`chi-sepnet` is a network, so those need the image with the model weights
(`algorithms/_qsmxt/models.Dockerfile`; `qsmrs_models: true` on a pair).
