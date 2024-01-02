#!/usr/bin/env bash

set -e

export ALGO_NAME="${1%.sh}"

if [ "$2" == "--simple" ]; then
    # simulate datasets with simple phantom
    bash datasets/simple_phantom.sh
elif [ "$2" == "--head" ]; then
    # simulate datasets with head phantom
    bash datasets/head_phantom.sh
fi

# run reconstruction
bash algos/${ALGO_NAME}.sh

# metrics
bash metrics/metrics.sh

# upload to object storage
bash upload.sh

