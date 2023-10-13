#!/usr/bin/env bash

set -e

# simulate datasets
bash datasets/simple_phantom.sh
# bash datasets/head_phantom.sh

# run reconstruction
bash algos/$1

# metrics
bash metrics/metrics.sh

# upload to object storage
bash upload.sh

