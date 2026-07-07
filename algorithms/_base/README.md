# Reference submission base image

Deps-only image (`numpy`, `scipy`, `nibabel`) shared by the in-repo reference submissions
(`tkd`, `tikhonov`, `sharp`, `nobfr-baseline`). Each of those bakes its `recon.py` + `run.sh` on top.
External submissions bring their own image instead — this is just to keep the examples small.
