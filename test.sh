#!/usr/bin/env bash

# install dependencies
pip install qsm-forward webdavclient3

# download head-phantom-maps
python get-maps.py
tar xf head-phantom-maps.tar
rm head-phantom-maps.tar

# generate bids data
qsm-forward head-phantom-maps/ bids

