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

In addition to quantitative metrics, qualitative evaluation is conducted through a visual comparison platform hosted at https://qsm-ci.b4a.app/. Users can view and compare the anonymized results from different pipelines and assist in ranking their preferences.

# Submitting your algorithm/pipeline

To participate, follow these steps:

1. **Fork the repository**: Fork this GitHub repository to your GitHub account.
2. **Add your pipeline**: Create a new directory for your pipeline containing in the `algos/` directory and format your pipeline according to the [Pipeline requirements](#pipeline-requirements).
3. **Test your pipeline**: Test your pipeline locally. Follow the instructions in [Testing locally](#testing-locally)
3. **Create a pull request**: Submit a pull request. Once accepted, the GitHub Action will automatically trigger to test your pipeline.

## Pipeline requirements

After cloning the QSM-CI repository using `git clone https://github.com/QSMxT/QSM-CI.git`, create a directory under `algos/` for your pipeline, add a Bash script called `main.sh` that will be used to run the pipeline.

The `main.sh` file is the starting point for your pipeline's execution on QSM-CI. After you submit your pipeline, it will automatically execute in the Docker container specified in the directive towards the top of the script (see the example script below). If you wish to use a different container, simply specify it by changing the directive. 

When the container is run, the `main.sh` script will be executed within a directory containing the script and any other files included in your pipeline directory. The demo `main.sh` file below, for example, requires `install_packages.jl` and `pipeline.jl` scripts alongside `main.sh`. Additionally, there will be a `bids/` directory available that contains input data, and an `output/` directory that should store your final NIfTI output volume once the script has completed.

The `main.sh` file should be structured as follows:

1. Run directives specify the shell and the Docker container for the pipeline to run with.
2. A reference list properly cites any algorithms used using comments.
2. Dependencies not already available in the container are installed.
3. The pipeline is executed against the simulated data available in the [BIDS](https://bids-specification.readthedocs.io/)-compliant `bids/` directory.
4. The final outputs of the pipeline are converted to NIfTI and placed in the `output/` directory.

To test your pipeline, please see [Testing locally](#testing-locally).

See below for a complete and working example:

```bash
#!/usr/bin/env bash
#DOCKER_IMAGE=ubuntu:latest

# == References ==
# - Unwrapping algorithm - Laplacian: Schofield MA, Zhu Y. Fast phase unwrapping algorithm for interferometric applications. Optics letters. 2003 Jul 15;28(14):1194-6. doi:10.1364/OL.28.001194")
# - Unwrapping algorithm - Laplacian: Zhou D, Liu T, Spincemaille P, Wang Y. Background field removal by solving the Laplacian boundary value problem. NMR in Biomedicine. 2014 Mar;27(3):312-9. doi:10.1002/nbm.3064")
# - Background field removal - V-SHARP: Wu B, Li W, Guidon A et al. Whole brain susceptibility mapping using compressed sensing. Magnetic resonance in medicine. 2012 Jan;67(1):137-47. doi:10.1002/mrm.23000
# - QSM algorithm - RTS: Kames C, Wiggermann V, Rauscher A. Rapid two-step dipole inversion for susceptibility mapping with sparsity priors. Neuroimage. 2018 Feb 15;167:276-83. doi:10.1016/j.neuroimage.2017.11.018
# - Julia package - NIfTI: JuliaNeuroscience. GitHub; 2021. https://github.com/JuliaNeuroscience/NIfTI.jl
# - Julia package - QSM: Kames C. kamesy/QSM.jl. GitHub; 2024. https://github.com/kamesy/QSM.jl

echo "[INFO] Downloading Julia"
apt-get update
apt-get install wget -y
wget https://julialang-s3.julialang.org/bin/linux/x64/1.9/julia-1.9.4-linux-x86_64.tar.gz
tar xf julia-1.9.4-linux-x86_64.tar.gz

echo "[INFO] Installing Julia packages"
julia-1.9.4/bin/julia install_packages.jl

echo "[INFO] Starting reconstruction with QSM.jl"
julia-1.9.4/bin/julia pipeline.jl

echo "[INFO] Moving output to expected location
mv out.nii.gz output/laplacian_vsharp_rts.nii.gz
```

# Testing locally

To test a pipeline locally, you first need a [BIDS](https://bids-specification.readthedocs.io/)-compliant dataset. You can use an existing dataset or simulate one using the [`qsm-forward`](https://github.com/astewartau/qsm-forward) pip package as described below.

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

Testing a pipeline locally requires a Linux or MacOS environment, or Windows Subsystem for Linux (WSL). It also requires Docker, Python, and pip. Please ensure these dependencies are available before attempting to test a pipeline locally. Additionally, please ensure you have your BIDS-complient directory ready in the QSM-CI repository folder.

You can test and evaluate a pipeline using the following, run from the QSM-CI repository's root directory (replace `${PIPELINE}` with the name of the desired pipeline - this should match the folder name):

```bash
./run.sh algos/${PIPELINE}
```

To produce quantitative metrics, several more dependencies are needed. First, run:

```bash
pip install argparse numpy nibabel scikit-learn scikit-image scipy
```

Then, to evaluate (replacing `${PIPELINE}` with your desired pipeline and `${RESULT}` with the filename of the NIfTI result):

```bash
python metrics/metrics.py \
    "bids/derivatives/qsm-forward/sub-1/anat/sub-1_Chimap.nii" \
    output/${PIPELINE}.nii.gz \
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

