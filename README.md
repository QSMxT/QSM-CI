# QSM-CI

## Introduction

Welcome to the Quantitative Susceptibility Mapping (QSM) Online Challenge (QSM-CI)! This initiative aims to continually evaluate QSM algorithms and pipelines openly and continuously to remain up-to-date with advancements.

Key features:

- **Always-Online submissions**: Submit and update your QSM pipelines anytime.
- **Full QSM pipeline**: Submitted QSM pipelines perform all steps from multi-echo combination, phase unwrapping, background field removal and dipole inversion. If you just want to submit an algorithm for one of these steps, you can construct a pipeline that includes it and substitute in your preferred algorithms for each of the other steps.
- **Automated testing**: Pipelines are automatically evaluated using GitHub Actions on simulated data.
- **Quantitative metrics**: A series of metrics are automatically computed to assess pipeline performance.
- **Qualitative metrics**: Visual comparison through user-based qualitative metrics using the Elo rating system.

## Metrics

### Quantitative

Submitted pipelines are evaluated using the following quantitative metrics:

- RMSE (root mean square error)
- NRMSE (normalized root mean square error)
- HFEN (high-frequency error norm)
- MAD (mean absolute deviation)
- CC (cross-correlation)
- XSIM (QSM cross-correlation)
- NMI (normalized mutual information)
- GXE (gradient difference error)

### Qualitative

In addition to quantitative metrics, qualitative evaluation is conducted through a visual comparison platform hosted at https://elocompare.b4a.app/. Users can view and compare the anonymized results from different pipelines and assist in ranking their preferences.

## Submitting your algorithm/pipeline

To participate, follow these steps:

1. **Fork the Repository**: Fork this GitHub repository to your GitHub account.
2. **Add Your Pipeline**: Create a new Bash script for your pipeline and add it to the `algos/` directory in your fork.
3. **Create a Pull Request**: Submit a pull request. Once accepted, the GitHub Action will automatically trigger to test your pipeline.

### Pipeline requirements

Submit your pipeline as a bash script in the `algos/` directory.

- The name of the script should uniquely describe your pipeline.
- Submitted algorithms should include the name, step(s) performed, authors including corresponding author details, and optionally a link to a paper and website or code repository.
- The pipeline should run against the [BIDS](https://bids.neuroimaging.io/) dataset, which will be available in the local `bids/` directory when the action runs.
- Results should be stored as NIfTI files in the output `recons/${ALGO_NAME}` directory on completion.

Please see the following as a minimal example:

```bash
#!/usr/bin/env bash

# 
# Submission: tgv.sh
# 
# Original works:
# 
#  - Fast, Robust and Improved Quantitative Susceptibility Mapping using Total Generalized Variation
#      Authors: Eckstein K, Stewart A, Bredies K, Langkammer C, Pfeuffer J, Tourell M, Jin J, O'Brien K, Barth M, Bollmann S
#      Corresponding author: Korbinian Eckstein <korbinian.eckstein@gmail.com>
#      Algorithm step(s): Dipole-inversion
#      Paper [optional]: https://doi.org/.../
#      Website [optional]: https://github.com/korbinian90/QuantitativeSusceptibilityMappingTGV.jl
#

# exit on error (do not change this line)
set -e

# create output directory (do not change this line)
mkdir -p "recons/${ALGO_NAME}"

# prepare dependencies (change to suit your pipeline)
echo "[INFO] Pulling QSMxT image"
sudo docker pull vnmd/qsmxt_6.2.0:20231012

echo "[INFO] Creating QSMxT container"
docker create --name qsmxt-container -it -v $(pwd):/tmp vnmd/qsmxt_6.2.0:20231012 /bin/bash

echo "[INFO] Starting QSMxT container"
docker start qsmxt-container

# run QSM pipeline (change to suit your pipeline)
echo "[INFO] Starting QSM reconstruction"
docker exec qsmxt-container bash -c "qsmxt /tmp/bids/ /tmp/qsmxt_output --premade bet --qsm_algorithm tgv --auto_yes --use_existing_masks" 

# collect results (change to suit your pipeline)
echo "[INFO] Collecting QSMxT results"
if ls qsmxt_output/qsm/*.nii 1> /dev/null 2>&1; then
    sudo gzip -f qsmxt_output/qsm/*.nii
fi
sudo mv qsmxt_output/qsm/*.nii.gz "recons/${ALGO_NAME}/${ALGO_NAME}.nii.gz"

# cleanup (change to suit your pipeline)
echo "[INFO] Deleting old outputs"
sudo rm -rf qsmxt_output/
```

## Testing locally

To test a pipeline locally, you will need at least Python v3.8. Several of the existing pipelines also use Docker, so if you wish to test one of these, you must also install Docker and have the Docker daemon running.

To test, run the `recon_and_eval.sh` script with the algorithm of your choice. The algorithm names are the filenames of the scripts in the `algos/` directory without file extensions. You also need to either simulate a BIDS dataset or provide one yourself for testing. 

### Simulated 'test-tube' phantom

QSM-CI provides a simple 'test-tube' phantom that you can generate using the `--simple` flag. For example:

```bash
./recon_and_eval.sh romeo_vsharp_rts --simple
```

### Realistic in-silico head phantom

To generate the more realistic head phantom, you should use the `--head` option. You will also need to provide the `data/` directory from the [realistic in-silico head phantom](https://doi.org/10.34973/m20r-jt17) repository with permission from the authors, and place it in the working directory:

```bash
./recon_and_eval.sh romeo_vsharp_rts --head
```

### Custom BIDS dataset

If you have your own BIDS dataset you would like to test, simply omit the simulation options:

```bash
./recon_and_eval.sh romeo_vsharp_rts
```

