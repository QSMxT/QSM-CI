#!/usr/bin/env bash

set -e

# get algo name
export ALGO_NAME="${1%.sh}"

# run reconstruction
bash algos/${ALGO_NAME}.sh

# compute metrics
bash metrics/metrics.sh

# upload to object storage
bash upload.sh

