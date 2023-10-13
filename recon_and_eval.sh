#!/usr/bin/env bash

set -e

# simulate datasets
bash datasets/simple_phantom.sh
# bash datasets/head_phantom.sh

# run reconstruction
bash algos/$1.sh

# metrics
bash metrics/metrics.sh

