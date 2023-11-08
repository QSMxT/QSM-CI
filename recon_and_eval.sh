#!/usr/bin/env bash

set -e

export ALGO_NAME="${1%.sh}"

# simulate datasets
# bash datasets/simple_phantom.sh
bash datasets/head_phantom.sh

# run reconstruction
bash algos/${ALGO_NAME}.sh

# metrics
bash metrics/metrics.sh

# upload to object storage
bash upload.sh

