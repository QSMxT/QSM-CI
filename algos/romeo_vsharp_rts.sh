#!/usr/bin/env bash

set -e

# create output directory
mkdir -p "recons/${ALGO_NAME}"

echo "[INFO] Pulling QSMxT image"
sudo docker pull vnmd/qsmxt_6.2.0:20231012

echo "[INFO] Creating QSMxT container"
docker create --name qsmxt-container -it -v $(pwd):/tmp vnmd/qsmxt_6.2.0:20231012 /bin/bash

echo "[INFO] Starting QSMxT container"
docker start qsmxt-container

echo "[INFO] Starting QSM reconstruction"
docker exec qsmxt-container bash -c "qsmxt /tmp/bids/ /tmp/qsmxt_output --premade fast -auto_yes --use_existing_masks"

echo "[INFO] Collecting QSMxT results"
gzip qsmxt_output/qsm/*.nii*
sudo mv qsmxt_output/qsm/*.nii.gz "recons/${ALGO_NAME}/${ALGO_NAME}.nii.gz"

echo "[INFO] Deleting old outputs"
sudo rm -rf qsmxt_output/

#end