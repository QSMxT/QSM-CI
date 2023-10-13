#!/usr/bin/env bash

set -e

# Check if Python is installed and if not install it
if command -v python >/dev/null 2>&1; then
    echo "Python is already installed."
else
    echo "Python is not installed. Installing..."
    sudo apt-get update
    sudo apt-get install python3 python-is-python3 -y
fi

# install dependencies
echo "[INFO] Downloading dependencies"
pip install qsm-forward==0.18 webdavclient3
export PATH=$PATH:/home/runnerx/.local/bin

# download head-phantom-maps
echo "[INFO] Downloading test data"
python get-maps.py
tar xf head-phantom-maps.tar
rm head-phantom-maps.tar

# generate bids data
echo "[INFO] Simulating BIDS dataset"
qsm-forward head-phantom-maps/ bids
rm -rf head-phantom-maps/

