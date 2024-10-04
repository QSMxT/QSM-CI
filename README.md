# QSM-CI Introduction

![QSM-CI Logo](img/QSM-CI-small.png)

Welcome to the Quantitative Susceptibility Mapping (QSM) Online Challenge (QSM-CI)! This initiative aims to continually and transparently integrate (CI) and evaluate QSM algorithms and pipelines to remain up-to-date with advancements.

[![](img/button.png)](https://forms.gle/spuRTVp5i6FUXbif7)

Key features:

- **Always-Online submissions**: Submit and update QSM pipelines at any time.
- **Full QSM pipeline**: Submitted QSM pipelines perform all steps from multi-echo combination, phase unwrapping, background field removal and dipole inversion. If you just want to submit an algorithm for one of these steps, you can construct a pipeline that includes it and substitute in your preferred algorithms for each of the other steps.
- **Automated testing**: Pipelines are automatically evaluated using GitHub Actions on simulated data, currently running on ARDC cloud resources.
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
- XSIM (structural similarity adjusted for QSM)
- NMI (normalized mutual information)
- GXE (gradient difference error)

## Qualitative

In addition to quantitative metrics, qualitative evaluation is conducted through a visual comparison platform hosted at https://qsm-ci.b4a.app/. Users can view and compare the anonymized results from different pipelines and assist in ranking their preferences.

# Submitting your algorithm/pipeline

To participate, follow these steps:

1. **Fork the repository**: Fork this GitHub repository to your GitHub account.
2. **Add your pipeline**: Create a new directory for your pipeline in the `algos/` directory and format your pipeline according to the [Pipeline requirements](#pipeline-requirements).
3. **Test your pipeline**: Test your pipeline locally. Follow the instructions in [Testing locally](#testing-locally)
3. **Create a pull request**: Submit a pull request. Once accepted, the GitHub Action will automatically trigger to test your pipeline.

## Pipeline requirements

After cloning the QSM-CI repository using `git clone https://github.com/QSMxT/QSM-CI.git`, install the QSM-CI pip package via `pip install -e .` or `pip install qsm-ci`. Then, create a directory under `algos/` for your pipeline, add a Bash script called `main.sh` that will be used to run the pipeline.

The `main.sh` file is the starting point for your pipeline's execution on QSM-CI. After you submit your pipeline, it will automatically execute in the Docker or Apptainer container specified in the directive towards the top of the script (see the example script below). If you wish to use a different container, simply specify it by changing the directive. 

When the container is run, the `main.sh` script will be executed within a directory containing the script and any other files included in your pipeline directory. The demo `main.sh` file below, for example, makes use of supplementary scripts `install_packages.jl` and `pipeline.jl`. Additionally, there will be a `bids/` directory available that contains input data, an `inputs.json` file that will contain paths to necessary files for QSM reconstruction, and an `output/` directory that should store your final NIfTI output volume once the script has completed. For example:

```
├── bids/
│   └── sub-1
│       └── ...
│       └── ...
│   └── ...
│── output/
├── inputs.json
└── main.sh
```

The following is an example of `inputs.json`:

```json
{
    "Subject": "1",
    "Session": null,
    "Acquisition": null,
    "Run": null,
    "phase_nii": [
        "bids/sub-1/anat/sub-1_echo-1_part-phase_MEGRE.nii",
        "bids/sub-1/anat/sub-1_echo-2_part-phase_MEGRE.nii",
        "bids/sub-1/anat/sub-1_echo-3_part-phase_MEGRE.nii",
        "bids/sub-1/anat/sub-1_echo-4_part-phase_MEGRE.nii"
    ],
    "phase_json": [
        "bids/sub-1/anat/sub-1_echo-1_part-phase_MEGRE.json",
        "bids/sub-1/anat/sub-1_echo-2_part-phase_MEGRE.json",
        "bids/sub-1/anat/sub-1_echo-3_part-phase_MEGRE.json",
        "bids/sub-1/anat/sub-1_echo-4_part-phase_MEGRE.json"
    ],
    "mag_nii": [
        "bids/sub-1/anat/sub-1_echo-1_part-mag_MEGRE.nii",
        "bids/sub-1/anat/sub-1_echo-2_part-mag_MEGRE.nii",
        "bids/sub-1/anat/sub-1_echo-3_part-mag_MEGRE.nii",
        "bids/sub-1/anat/sub-1_echo-4_part-mag_MEGRE.nii"
    ],
    "mag_json": [
        "bids/sub-1/anat/sub-1_echo-1_part-mag_MEGRE.json",
        "bids/sub-1/anat/sub-1_echo-2_part-mag_MEGRE.json",
        "bids/sub-1/anat/sub-1_echo-3_part-mag_MEGRE.json",
        "bids/sub-1/anat/sub-1_echo-4_part-mag_MEGRE.json"
    ],
    "EchoTime": [
        0.004,
        0.012,
        0.02,
        0.028
    ],
    "MagneticFieldStrength": 7,
    "Derivatives": {
        "qsm-forward": {
            "Chimap": [
                "bids/derivatives/qsm-forward/sub-1/anat/sub-1_Chimap.nii"
            ],
            "dseg": [
                "bids/derivatives/qsm-forward/sub-1/anat/sub-1_dseg.nii"
            ]
        }
    },
    "mask": "bids/derivatives/qsm-forward/sub-1/anat/sub-1_mask.nii"
}
```

The `main.sh` file should be structured as follows:

1. Run directives specify the shell and the Docker container for the pipeline to run with.
2. A reference list properly cites any algorithms used using comments.
2. Dependencies not already available in the container are installed.
3. The pipeline is executed against the requested files from inputs.json, which will derive from the data available in the [BIDS](https://bids-specification.readthedocs.io/)-compliant `bids/` directory.  
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
        ├── sub-1_echo-1_part-mag_MEGRE.json
        ├── sub-1_echo-1_part-mag_MEGRE.nii
        ├── sub-1_echo-1_part-phase_MEGRE.json
        ├── sub-1_echo-1_part-phase_MEGRE.nii
        ├── sub-1_echo-2_part-mag_MEGRE.json
        ├── sub-1_echo-2_part-mag_MEGRE.nii
        ├── sub-1_echo-2_part-phase_MEGRE.json
        ├── sub-1_echo-2_part-phase_MEGRE.nii
        ├── sub-1_echo-3_part-mag_MEGRE.json
        ├── sub-1_echo-3_part-mag_MEGRE.nii
        ├── sub-1_echo-3_part-phase_MEGRE.json
        ├── sub-1_echo-3_part-phase_MEGRE.nii
        ├── sub-1_echo-4_part-mag_MEGRE.json
        ├── sub-1_echo-4_part-mag_MEGRE.nii
        ├── sub-1_echo-4_part-phase_MEGRE.json
        └── sub-1_echo-4_part-phase_MEGRE.nii
```

### Realistic in-silico head phantom

To generate input data using the head phantom, you should use the `head` option in `qsm-forward`. You will also need to provide the `data/` directory from the [realistic in-silico head phantom](https://doi.org/10.34973/m20r-jt17) repository (Marques, J. P., 2021) with permission from the authors, and place it in the working directory. It should be structured as follows:

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
        ├── sub-1_echo-1_part-mag_MEGRE.json
        ├── sub-1_echo-1_part-mag_MEGRE.nii
        ├── sub-1_echo-1_part-phase_MEGRE.json
        ├── sub-1_echo-1_part-phase_MEGRE.nii
        ├── sub-1_echo-2_part-mag_MEGRE.json
        ├── sub-1_echo-2_part-mag_MEGRE.nii
        ├── sub-1_echo-2_part-phase_MEGRE.json
        ├── sub-1_echo-2_part-phase_MEGRE.nii
        ├── sub-1_echo-3_part-mag_MEGRE.json
        ├── sub-1_echo-3_part-mag_MEGRE.nii
        ├── sub-1_echo-3_part-phase_MEGRE.json
        ├── sub-1_echo-3_part-phase_MEGRE.nii
        ├── sub-1_echo-4_part-mag_MEGRE.json
        ├── sub-1_echo-4_part-mag_MEGRE.nii
        ├── sub-1_echo-4_part-phase_MEGRE.json
        └── sub-1_echo-4_part-phase_MEGRE.nii
```

## Running and evaluating a pipeline

Running a pipeline locally requires a Linux or MacOS environment, or Windows Subsystem for Linux (WSL). It also requires Docker or Apptainer, as well as Python and pip. Please ensure these dependencies are available before attempting to test a pipeline locally. Additionally, please ensure you have your BIDS-complient directory ready as described above.

First, make sure to install QSM-CI using either `pip install qsm-ci` (or `pip install -e .` from the repository directory). 

Then, you can run a pipeline using the `qsm-ci run` command:

```bash
qsm-ci run <PIPELINE_DIR> <BIDS_DIR> <WORK_DIR>
```

For example:

```bash
qsm-ci run algos/laplacian_vsharp_rts bids work
```

By default, containers are run using Docker. You can also use Apptainer (singularity) by changing the container engine:

```bash
qsm-ci run algos/laplacian_vsharp_rts bids work --container_engine apptainer
```

Then, to evaluate, you can use `qsm-ci eval` against a ground truth QSM file and a reconstruction, using a mask to constrain the evaluation:

```bash
qsm-ci eval \
    --ground_truth bids/qsm-forward/sub-1/anat/sub-1_Chimap.nii \
    --estimate bids/laplacian_vsharp_rts/sub-1/anat/sub-1_Chimap.nii \
    --roi bids/qsm-forward/sub-1/anat/sub-1_mask.nii \
    --output_dir output
```

This will generate a series of metrics output files alongside the result in several formats (CSV, JSON and markdown).

For example:

```bash
$ tree output/
output/
└── romeo_vsharp_rts
    ├── metrics.csv
    ├── metrics.json
    ├── metrics.md
    └── romeo_vsharp_rts.nii.gz
$ cat output/metrics.json
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

