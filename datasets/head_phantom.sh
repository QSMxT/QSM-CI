#!/usr/bin/env bash

set -e

echo "[INFO] Setting up head phantom dataset..."

# check python
echo "[INFO] Checking for Python >=3.8..."
if ! command -v python >/dev/null 2>&1; then
    echo "Python >=3.8 is required. Please install it and try again."
    exit 1
fi

# install other dependencies
echo "[INFO] Downloading dependencies..."
pip install qsm-forward==0.22 osfclient --user --break-system-packages

# get data from osf
if [ -d "data" ]; then
    echo "[INFO] Existing data/ folder already found - skipping download."
else
    echo "[INFO] data/ folder not found - attempting download..."
    echo "[INFO] === DOWNLOAD REQUIRES GITHUB SECRET: OSF_TOKEN ==="
    osf --project 9jc42 fetch data.tar

    echo "[INFO] Extracting data.tar to data/..."
    tar xf data.tar
    rm data.tar
fi

# generate bids data
if [ -d "bids" ]; then
    echo "[INFO] Existing bids/ folder already found - skipping generation."
else
    echo "[INFO] Simulating BIDS dataset using head phantom data..."
    qsm-forward head data/ bids/
fi

echo "[INFO] Head phantom dataset setup complete."

