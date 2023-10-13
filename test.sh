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
echo "[INFO] Downloading dependencies"
pip install qsm-forward==0.18 webdavclient3
export PATH=$PATH:/home/runnerx/.local/bin

sudo apt-get update
sudo apt-get install tree

# generate bids data
echo "[INFO] Simulating BIDS dataset"
qsm-forward simple bids

# create output directory
mkdir recons/

# install qsmxt
echo "[INFO] Pulling QSMxT image"
sudo docker pull vnmd/qsmxt_5.1.0:20230905

echo "[INFO] Creating QSMxT container"
docker create --name qsmxt-container -it -v $(pwd):/tmp vnmd/qsmxt_5.1.0:20230905 /bin/bash

echo "[INFO] Starting QSMxT container"
docker start qsmxt-container

# do reconstruction using qsmxt
echo "[INFO] Starting QSM reconstruction"
docker exec qsmxt-container bash -c "qsmxt /tmp/bids/ /tmp/qsmxt_output --premade fast --masking_algorithm threshold --masking_input phase --auto_yes"

echo "[INFO] Collecting QSMxT results"
sudo rm -rf qsmxt_output/workflow
sudo mv qsmxt_output/qsm recons/qsmxt
sudo rm -rf qsmxt_output/
tree recons/

# run metrics + generate figure - pass command-line arguments
python metrics.py \
    --ground_truth "bids/derivatives/qsm-forward/sub-1/anat/sub-1_Chimap.nii" \
    --recon "recons/qsmxt/qsm/*.nii" \
    --roi "bids/derivatives/qsm-forward/sub-1/anat/sub-1_mask.nii"

# display figure to github
cat *.csv
cat *.md

