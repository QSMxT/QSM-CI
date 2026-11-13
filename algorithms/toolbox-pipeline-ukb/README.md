# UK Biobank pipeline (toolbox-pipeline reference)

The reference for QSMxT's `uk-biobank` toolbox pipeline in pipeline parity
([QSMxT/QSM-CI#421](https://github.com/QSMxT/QSM-CI/issues/421)). It is the `ukb-qsm` submission's
image and code ([`../ukb-qsm/`](../ukb-qsm/README.md): `recon.m`, the vendored UK Biobank code, the
build and its fidelity check), entered once more under the `toolbox-pipeline` algorithm so that it
pairs with `toolbox-pipeline-qsmrs`. Every difference from upstream's `UKBiobank_QSM.m` is listed
in `ukb-qsm`'s README.

It takes the dataset's brain mask, because UK Biobank's own comes from its T1 pipeline: in the pair
the candidate is given the same mask (`dataset_mask`), so both sides start from it and everything
after (both phase-reliability trims, unwrapping, echo combination, V-SHARP, iLSQR) is compared.
