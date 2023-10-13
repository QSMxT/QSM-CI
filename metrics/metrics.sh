#!/usr/bin/env bash

set -e

# Check if Python is installed and if not install it
if command -v python >/dev/null 2>&1; then
    echo "Python is already installed."
else
    echo "Python is not installed. Installing..."
    sudo apt-get update
    sudo apt-get install python3 python-is-python3 -y
fi

# install dependencies
pip install argparse numpy nibabel scikit-learn scikit-image scipy

# run metrics
python metrics/metrics.py \
    "bids/derivatives/qsm-forward/sub-1/anat/sub-1_Chimap.nii" \
    recons/${ALGO_NAME}/*.nii* \
    --roi "bids/derivatives/qsm-forward/sub-1/anat/sub-1_mask.nii"

# display figure to github
cat recons/${ALGO_NAME}/*.md* >> $GITHUB_STEP_SUMMARY

