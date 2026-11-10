# FSL BET2 (original of QSM.rs's BET)

`bet2` from Bostrix/FSL-BET2 d5acd7f, the commit `qsm_core::bet` cites, built from source in
`Dockerfile`.

## Licence

The repository has no LICENSE file of its own. Its source carries the FSL Release 5.0 licence
(`bet2.cpp` header, University of Oxford): use is non-commercial only, and a transfer is allowed
when it is "done without financial return, the conditions of this Licence are imposed upon the
receiver of the product, and all original and amended source code is included in any transmitted
product".

QSM-CI's position (Ashley, 2026-11-10): an image containing bet2 may be published publicly, as
Neurodesk publishes FSL, when it carries the full source it was built from and the licence text,
names the licence in its OCI label (`org.opencontainers.image.licenses`), and says so in its
README. This image keeps the full source in `/opt/FSL-BET2`; the toolbox-pipeline references that
contain bet2 (`toolbox-pipeline-qsmart`, and MEDI's bet2 mex in `toolbox-pipeline-medi-cornell`,
`toolbox-pipeline-chisep`, `toolbox-pipeline-decompose-qsmci`) carry theirs the same way. (This
replaces the earlier local-only position; QSM.rs's `THIRD_PARTY_NOTICES.md` is about PRELUDE's
source in QSM.rs and is unaffected.)

## Use

```bash
podman build -t localhost/qsm-ci/bet2:d5acd7f algorithms/_bet2
bash algorithms/_bet2/bet.sh IN.nii.gz OUT -f 0.2     # in the image: writes OUT.nii.gz, OUT_mask.nii.gz
```

This fork always writes `<out>_mask`; its `-m` takes a file name, where FSL's is a flag, so
`bet.sh` does not pass it. Fidelity and the first look against QSM.rs are in
[`fidelity/cpp-py`](../../fidelity/cpp-py/README.md) (`--ops bet-f0.2,bet-f0.5`).

This image itself is still built locally (it has no `brain-extraction` entry and is not pushed);
under the position above it could be published the same way if one is added.
