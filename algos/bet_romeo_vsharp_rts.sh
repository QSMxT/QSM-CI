#!/usr/bin/env bash

set -e

# create output directory
mkdir recons/

# install qsmxt
echo "[INFO] Pulling QSMxT image"
sudo docker pull vnmd/qsmxt_6.2.0:20231012

echo "[INFO] Creating QSMxT container"
docker create --name qsmxt-container -it -v $(pwd):/tmp vnmd/qsmxt_6.2.0:20231012 /bin/bash

echo "[INFO] Starting QSMxT container"
docker start qsmxt-container

# do reconstruction using qsmxt
echo "[INFO] Starting QSM reconstruction"
docker exec qsmxt-container bash -c "qsmxt /tmp/bids/ /tmp/qsmxt_output --premade fast --masking_algorithm threshold --masking_input phase --auto_yes"

echo "[INFO] Collecting QSMxT results"
sudo rm -rf qsmxt_output/workflow
sudo mv qsmxt_output/qsm recons/qsmxt
sudo rm -rf qsmxt_output/

