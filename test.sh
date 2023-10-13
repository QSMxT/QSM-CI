#!/usr/bin/env bash

set -e

# simulate datasets
bash datasets/simple_phantom.sh
# bash datasets/head_phantom.sh

# run reconstruction
bash algos/romeo_vsharp_rts.sh

# metrics
bash metrics/metrics.sh

