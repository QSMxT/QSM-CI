#!/usr/bin/env bash

set -e

# install dependencies
echo "[INFO] Downloading dependencies"
pip install qsm-forward webdavclient3

# download head-phantom-maps
echo "[INFO] Downloading test data"
python get-maps.py
tar xf head-phantom-maps.tar
rm head-phantom-maps.tar

# generate bids data
echo "[INFO] Simulating BIDS dataset"
qsm-forward head-phantom-maps/ bids

