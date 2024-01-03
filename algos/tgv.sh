#!/usr/bin/env bash

set -e

# create output directory 
PIPELINE_NAME="$(basename "$0" .sh)"
mkdir -p "recons/${PIPELINE_NAME}"

echo "[INFO] Pulling QSMxT image"
sudo docker pull vnmd/qsmxt_6.2.0:20231012

echo "[INFO] Creating QSMxT container"
sudo docker create --name qsmxt-container -it -v $(pwd):/tmp vnmd/qsmxt_6.2.0:20231012 /bin/bash

echo "[INFO] Starting QSMxT container"
sudo docker start qsmxt-container

echo "[INFO] Starting QSM reconstruction"
sudo docker exec qsmxt-container bash -c "qsmxt /tmp/bids/ /tmp/qsmxt_output --premade bet --qsm_algorithm tgv --auto_yes --use_existing_masks" 

echo "[INFO] Collecting QSMxT results"
if ls qsmxt_output/qsm/*.nii 1> /dev/null 2>&1; then
    sudo gzip -f qsmxt_output/qsm/*.nii
fi
sudo mv qsmxt_output/qsm/*.nii.gz "recons/${PIPELINE_NAME}/${PIPELINE_NAME}.nii.gz"

echo "[INFO] Deleting old outputs"
sudo rm -rf qsmxt_output/

