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

# create python virtual environment
python -m venv .venv/
source .venv/bin/activate

# install dependencies
echo "[INFO] Downloading dependencies"
pip install qsm-forward==0.19 webdavclient3
export PATH=$PATH:/home/runnerx/.local/bin

# generate bids data
echo "[INFO] Simulating BIDS dataset"
qsm-forward simple bids

