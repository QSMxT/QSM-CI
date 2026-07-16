# xQSM

Quantitative Susceptibility Mapping with an octave-convolutional, noise-regularized U-Net for
**dipole inversion**.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [xQSM](https://github.com/sunhongfu/xQSM) — PyTorch, **CPU-only** (no GPU)
- **Reference:** Gao Y., Zhu X., Moffat B.A., Glarin R., Wilman A.H., Pike G.B., Crozier S., Liu F., Sun H. (2021). *xQSM: quantitative susceptibility mapping with octave convolutional and noise-regularized neural networks.* NMR in Biomedicine, 34(3), e4461. (DOI: [10.1002/nbm.4461](https://doi.org/10.1002/nbm.4461))

## Why `dipole`

xQSM is a pretrained network that maps the **local (tissue) field** directly to **susceptibility**.
It performs dipole inversion only — it does no background field removal — so it sits in the `dipole`
stage: `consumes [localfield, mask, params]`, `produces [chimap]` (see `stages.yml`).

## Units

The QSM-CI `localfield` is an unwrapped frequency map already **in ppm** (normalized by B0), which is
what the xQSM in-vivo checkpoint was trained on. No rescaling is applied — the field is passed straight
through and the output susceptibility (ppm) is masked before saving.

## B0 direction, voxel size, matrix size

The repo's pure-Python inference (`inference.run_xqsm`) operates on the field map **directly**:

- **B0 direction / `z_prjs`** — not consumed by the Python path. The `xQSM_invivo` network is applied
  to the padded local field and adds a learned residual (`x = f(x) + x`); orientation is carried by the
  NIfTI affine, which inference reads from the input and writes unchanged onto the output. (`z_prjs`/
  `vox` are arguments of the repo's *MATLAB* wrappers, not this Python entrypoint.)
- **Voxel size** — carried by the NIfTI header/affine; not passed as a separate argument.
- **Matrix size** — the network zero-pads each dimension to a multiple of 8 internally and crops back
  afterwards, so there is no fixed input matrix size.

Consequently `run.sh` only forwards the local field and mask; `$QSMCI_B0_DIR` / `$QSMCI_VOXEL_SIZE`
are unused by this path.

## How QSM-CI runs it

```bash
python /opt/xQSM/run.py \
  --lfs  /input/localfield.nii.gz \
  --mask /input/mask.nii.gz \
  --output <tmp>
# run.py -> inference.run_xqsm writes <tmp>/xQSM.nii.gz, which run.sh moves to
# /output/chimap.nii.gz
```

The two pretrained checkpoints (`xQSM_invivo.pth` ~19 MB, `Unet_invivo.pth` ~15 MB) are **baked into
the image** at build time from the repo's `v1.0-demo` GitHub Release into `/opt/xQSM/python/` (where
`inference.py` expects them) so the scoring run works fully offline (`--network none`).

## Parameters

xQSM has no runtime tunables — it uses fixed pretrained weights and no acquisition-derived inputs on
the Python inference path.

## Building the image

The environment image is built from this folder. Scoring builds it at score-time, so no manual push is
needed for the leaderboard; a push is only needed for later Zenodo publishing:

```bash
docker build -t ghcr.io/astewartau/qsm-ci/xqsm:v1 algorithms/xqsm
docker push  ghcr.io/astewartau/qsm-ci/xqsm:v1
```

## License

The xQSM code and pretrained weights are used here **with the author's permission** (Hongfu Sun,
University of Queensland). See the [upstream repository](https://github.com/sunhongfu/xQSM) for terms.

_Citations/DOIs are auto-generated best-effort references and should be verified._
