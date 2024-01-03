#!/usr/bin/env bash

set -e

# check dependencies
if ! command -v python >/dev/null 2>&1; then
    echo "Python >=3.8 is required. Please install it and try again."
    exit 1
fi

# install other dependencies
echo "[INFO] Downloading dependencies"
pip install qsm-forward==0.19 webdavclient3

# generate bids data
echo "[INFO] Simulating BIDS dataset"
qsm-forward simple bids/

