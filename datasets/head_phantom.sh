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
python --version
python -m venv .venv/
source .venv/bin/activate

# install dependencies
echo "[INFO] Downloading dependencies"
pip install qsm-forward==0.19 webdavclient3
export PATH=$PATH:/home/runnerx/.local/bin

# download head phantom data
# first check if head phantom data folder exists already
if [ -d "data" ]; then
    echo "[INFO] data/ folder found."
else
    # Check if RDM_USER and RDM_KEY are set
    if [ -z "$RDM_USER" ] || [ -z "$RDM_KEY" ]; then
        echo "[ERROR] RDM_USER and/or RDM_KEY are not set! If you are running this on GitHub Actions, make sure you have set the secrets RDM_USER and RDM_KEY correctly. If you are running this locally, download the head phantom repository from https://doi.org/10.34973/m20r-jt17 and place the data/ directory here."
        exit 1
    fi
    echo "[INFO] Downloading head phantom maps"
    python get-maps.py
    tar xf data.tar
    rm data.tar
fi

# generate bids data
echo "[INFO] Simulating BIDS dataset"
qsm-forward head data/ bids

