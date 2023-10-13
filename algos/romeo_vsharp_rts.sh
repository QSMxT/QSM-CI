#!/usr/bin/env bash

set -e

# create output directory
mkdir -p recons/

# install qsmxt
echo "[INFO] Pulling QSMxT image"
sudo docker pull vnmd/qsmxt_6.2.0:20231012

echo "[INFO] Creating QSMxT container"
docker create --name qsmxt-container -it -v $(pwd):/tmp vnmd/qsmxt_6.2.0:20231012 /bin/bash

echo "[INFO] Starting QSMxT container"
docker start qsmxt-container

# do reconstruction using qsmxt
echo "[INFO] Starting QSM reconstruction"
docker exec qsmxt-container bash -c "qsmxt /tmp/bids/ /tmp/qsmxt_output --premade fast -auto_yes --use_existing_masks"

echo "[INFO] Collecting QSMxT results"
mkdir -p recons/qsmxt/
sudo rm -rf qsmxt_output/workflow
sudo mv qsmxt_output/qsm/*.nii recons/qsmxt
sudo rm -rf qsmxt_output/

