# QSM-CI Introduction

Welcome to the Quantitative Susceptibility Mapping (QSM) Online Challenge (QSM-CI)! This initiative aims to continually evaluate QSM algorithms and pipelines openly and continuously to remain up-to-date with advancements.

Key features:

- **Always-Online submissions**: Submit and update your QSM pipelines anytime.
- **Full QSM pipeline**: Submitted QSM pipelines perform all steps from multi-echo combination, phase unwrapping, background field removal and dipole inversion. If you just want to submit an algorithm for one of these steps, you can construct a pipeline that includes it and substitute in your preferred algorithms for each of the other steps.
- **Automated testing**: Pipelines are automatically evaluated using GitHub Actions on simulated data.
- **Quantitative metrics**: A series of metrics are automatically computed to assess pipeline performance.
- **Qualitative metrics**: Visual comparison through user-based qualitative metrics using the Elo rating system.

# Metrics

## Quantitative

Submitted pipelines are evaluated using the following quantitative metrics:

- RMSE (root mean square error)
- NRMSE (normalized root mean square error)
- HFEN (high-frequency error norm)
- MAD (mean absolute deviation)
- CC (cross-correlation)
- XSIM (QSM cross-correlation)
- NMI (normalized mutual information)
- GXE (gradient difference error)

## Qualitative

In addition to quantitative metrics, qualitative evaluation is conducted through a visual comparison platform hosted at https://elocompare.b4a.app/. Users can view and compare the anonymized results from different pipelines and assist in ranking their preferences.

# Submitting your algorithm/pipeline

To participate, follow these steps:

1. **Fork the repository**: Fork this GitHub repository to your GitHub account.
2. **Add your pipeline**: Create a new Bash script for your pipeline and add it to the `algos/` directory in your fork. Follow the instructions in [Pipeline requirements](#pipeline-requirements).
3. **Test your pipeline**: Test your pipeline locally. Follow the instructions in [Testing locally](#testing-locally)
3. **Create a pull request**: Submit a pull request. Once accepted, the GitHub Action will automatically trigger to test your pipeline.

## Pipeline requirements

Create your pipeline as a bash script in the `algos/` directory after cloning the repository using `git clone https://github.com/QSMxT/QSM-CI.git`. Begin by copying an existing pipeline such as [romeo_vsharp_rts.sh](https://github.com/QSMxT/QSM-CI/blob/main/algos/romeo_vsharp_rts.sh), renaming it, and adjusting as necessary. Importantly, please ensure the following:

- The name of the script should uniquely describe your pipeline.
- A list of references must be included as bash comments to clearly cite any algorithms and software used.
- The script should install or make available any relevant dependencies, though it may assume that Docker and Python are already available.
- The script should load input data from a local `bids/` directory that conforms to the [BIDS](https://bids.neuroimaging.io/) standard. A BIDS dataset can be generated by following the instructions in [Simulating data](#simulating-data). Currently, algorithms are assessed based on the [realistic in-silico head phantom](#realistic-in-silico-head-phantom) simulation.
- Results should be stored as NIfTI files in the output directory `recons/${PIPELINE_NAME}`.

# Testing locally

To test a pipeline, you first need a BIDS-formatted dataset. You can either use an existing dataset you have or simulate one using the [`qsm-forward`](https://github.com/astewartau/qsm-forward) pip package.

## Simulating data

First install [`qsm-forward`](https://github.com/astewartau/qsm-forward). Then, you can choose to either generate a simple 'test-tube' phantom consisting of cylindrical structures, each with a uniform susceptibility value, or using the [realistic in-silico head phantom](#realistic-in-silico-head-phantom). Currently, the head phantom simulation is used for online evaluation.

### Simulated 'test-tube' phantom

The `qsm-forward` package provides a simple 'test-tube' phantom that you can generate using:

```bash
qsm-forward simple bids/
```

The resulting BIDS directory should be structured as follows:

```
bids
├── derivatives
│   └── qsm-forward
│       └── sub-1
│           └── anat
│               ├── sub-1_Chimap.nii
│               ├── sub-1_dseg.nii
│               └── sub-1_mask.nii
└── sub-1
    └── anat
        ├── sub-1_echo-1_part-mag_T2starw.json
        ├── sub-1_echo-1_part-mag_T2starw.nii
        ├── sub-1_echo-1_part-phase_T2starw.json
        ├── sub-1_echo-1_part-phase_T2starw.nii
        ├── sub-1_echo-2_part-mag_T2starw.json
        ├── sub-1_echo-2_part-mag_T2starw.nii
        ├── sub-1_echo-2_part-phase_T2starw.json
        ├── sub-1_echo-2_part-phase_T2starw.nii
        ├── sub-1_echo-3_part-mag_T2starw.json
        ├── sub-1_echo-3_part-mag_T2starw.nii
        ├── sub-1_echo-3_part-phase_T2starw.json
        ├── sub-1_echo-3_part-phase_T2starw.nii
        ├── sub-1_echo-4_part-mag_T2starw.json
        ├── sub-1_echo-4_part-mag_T2starw.nii
        ├── sub-1_echo-4_part-phase_T2starw.json
        └── sub-1_echo-4_part-phase_T2starw.nii
```

### Realistic in-silico head phantom

To generate input data using the head phantom, you should use the `--head` option in `qsm-forward`. You will also need to provide the `data/` directory from the [realistic in-silico head phantom](https://doi.org/10.34973/m20r-jt17) repository (Marques, J. P., 2021) with permission from the authors, and place it in the working directory. It should be structured as follows:

```
data
├── chimodel
│   ├── ChiModelMIX.nii
│   └── ChiModelMIX_noCalc.nii
├── maps
│   ├── M0.nii.gz
│   ├── R1.nii.gz
│   └── R2star.nii.gz
└── masks
    ├── BrainMask.nii.gz
    ├── highgrad.nii.gz
    └── SegmentedModel.nii.gz
```

Provided the `data/` directory is available in the working directory, you can generate a BIDS dataset using:

```bash
qsm-forward head data/ bids/
```

**NOTE:** The head phantom simulation requires a large amount of RAM (12GB+). It is recommended that you close other applications such as web browsers before running this step.

The resulting BIDS directory should be structured as follows:

```
bids
├── derivatives
│   └── qsm-forward
│       └── sub-1
│           └── anat
│               ├── sub-1_Chimap.nii
│               ├── sub-1_dseg.nii
│               └── sub-1_mask.nii
└── sub-1
    └── anat
        ├── sub-1_echo-1_part-mag_T2starw.json
        ├── sub-1_echo-1_part-mag_T2starw.nii
        ├── sub-1_echo-1_part-phase_T2starw.json
        ├── sub-1_echo-1_part-phase_T2starw.nii
        ├── sub-1_echo-2_part-mag_T2starw.json
        ├── sub-1_echo-2_part-mag_T2starw.nii
        ├── sub-1_echo-2_part-phase_T2starw.json
        ├── sub-1_echo-2_part-phase_T2starw.nii
        ├── sub-1_echo-3_part-mag_T2starw.json
        ├── sub-1_echo-3_part-mag_T2starw.nii
        ├── sub-1_echo-3_part-phase_T2starw.json
        ├── sub-1_echo-3_part-phase_T2starw.nii
        ├── sub-1_echo-4_part-mag_T2starw.json
        ├── sub-1_echo-4_part-mag_T2starw.nii
        ├── sub-1_echo-4_part-phase_T2starw.json
        └── sub-1_echo-4_part-phase_T2starw.nii
```

## Testing and evaluating a pipeline

Once you have your BIDS directory ready, you can test and evaluate a pipeline using the following (replace `${PIPELINE}` with the desired pipeline name):

```bash
bash algos/${PIPELINE}.sh
```

To evaluate and check metrics, several more dependencies are needed. First, run:

```bash
pip install argparse numpy nibabel scikit-learn scikit-image scipy
```

Then, to evaluate (replacing `${PIPELINE}` with your desired pipeline and `${RESULT}` with the filename of the NIfTI result):

```bash
python metrics/metrics.py \
    "bids/derivatives/qsm-forward/sub-1/anat/sub-1_Chimap.nii" \
    recons/${PIPELINE}/${RESULT}.nii \
    --roi "bids/derivatives/qsm-forward/sub-1/anat/sub-1_mask.nii"
```

This will generate a series of metrics output files alongside the result in several formats (CSV, JSON and markdown).

For example:

```bash
$ python metrics/metrics.py \
    "bids/derivatives/qsm-forward/sub-1/anat/sub-1_Chimap.nii" \
    recons/romeo_vsharp_rts/romeo_vsharp_rts.nii.gz \
    --roi "bids/derivatives/qsm-forward/sub-1/anat/sub-1_mask.nii"
$ tree recons/
recons/
└── romeo_vsharp_rts
    ├── metrics.csv
    ├── metrics.json
    ├── metrics.md
    └── romeo_vsharp_rts.nii.gz
$ cat recons/metrics.json
{
    "RMSE": 0.02399989263113798,
    "NRMSE": 75.32962107000168,
    "HFEN": 0.9999502792081314,
    "MAD": 0.016960979964151173,
    "XSIM": 0.22089135754012057,
    "CC": [
        0.6593238301114027,
        0.0
    ],
    "NMI": 1.0891590556325916,
    "GXE": 0.6562468317212361
}
```

