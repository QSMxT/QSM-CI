# FSL BET2 (original of QSM.rs's BET): local only

`bet2` from Bostrix/FSL-BET2 d5acd7f, the commit `qsm_core::bet` cites, built from source in
`Dockerfile`. **Build it locally; do not publish the image.**

## Licence

The repository has no LICENSE file of its own. Its source carries the FSL Release 5.0 licence
(`bet2.cpp` header, University of Oxford):
- use is non-commercial only;
- "No part of the Software may be reproduced, modified, transmitted or transferred ... without the
  express permission of the University", except when that is "done without financial return, the
  conditions of this Licence are imposed upon the receiver of the product, and all original and
  amended source code is included in any transmitted product".

A public image on a registry has no way to impose the licence's conditions on whoever pulls it,
and anyone, commercial users included, could pull it. Redistribution is therefore not clearly
allowed, and the image stays local (it does keep the full source in `/opt/FSL-BET2`, as the
licence asks of a transfer). QSM.rs's `THIRD_PARTY_NOTICES.md` reaches the same view of FSL's
licence for PRELUDE. Publishing would need the University's permission.

## Use

```bash
podman build -t localhost/qsm-ci/bet2:d5acd7f algorithms/_bet2
bash algorithms/_bet2/bet.sh IN.nii.gz OUT -f 0.2     # in the image: writes OUT.nii.gz, OUT_mask.nii.gz
```

This fork always writes `<out>_mask`; its `-m` takes a file name, where FSL's is a flag, so
`bet.sh` does not pass it. Fidelity and the first look against QSM.rs are in
[`fidelity/cpp-py`](../../fidelity/cpp-py/README.md) (`--ops bet-f0.2,bet-f0.5`).

Because the image is not public, BET has no `brain-extraction` entry here (CI could not pull it),
and QSMART's masking pair (`brainmask.m`: N4 → `bet2 -f 0.2` → percentile threshold → morphology,
QSMxT/QSM-CI#295 step 4) is deferred.
