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
pip install osfclient h5py numpy nibabel --user --break-system-packages

# get data from osf
osf -p y6rc3 fetch osfstorage/subject1/1.mat


