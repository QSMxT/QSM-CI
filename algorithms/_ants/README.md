# ANTs N4 (original of QSM.rs's N4)

`ghcr.io/astewartau/qsm-ci/ants-n4:v1`
(`sha256:621644e172c4872f1d181c9c18dc8717c40aece19de8d28c31fce93028017c49`): the official ANTs
2.4.3 release binary of `N4BiasFieldCorrection` (ITK 5.3.0 linked in), the version
`qsm_core::utils::n4` cites. Not a QSM-CI stage: it runs as a fixture run
([`fidelity/cpp-py`](../../fidelity/cpp-py/README.md)), never scored.

- `n4.sh IN OUT [BIAS] [options]` runs `N4BiasFieldCorrection -i IN -o [OUT,BIAS]` with ANTs'
  defaults (QSMART's `brainmask.m` call; QSM.rs's `N4Params::default`), 4 ITK threads.
- **Licence:** ANTs and ITK are Apache-2.0; ANTs' `COPYING.txt` (v2.4.3) is in the image at
  `/opt/ants/COPYING.txt`. Redistribution in a public image is allowed.
