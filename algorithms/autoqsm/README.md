# AutoQSM

Learning-based **single-step** quantitative susceptibility mapping reconstruction **without brain
extraction**.

- **Stage:** `bfr+dipole` (totalfield → chimap, ppm)
- **Engine:** [AutoQSM](https://github.com/AMRI-Lab/AutoQSM) — a V-Net, **TensorFlow 1.15 / Keras
  2.2.5 / Python 3.6**, run **CPU-only** (no GPU)
- **Reference:** Wei H., Cao S., Zhang Y., Guan X., Yan F., Yeom K.W., Liu C. (2019). *Learning-based
  single-step quantitative susceptibility mapping reconstruction without brain extraction.*
  NeuroImage, 202, 116064. (DOI: [10.1016/j.neuroimage.2019.116064](https://doi.org/10.1016/j.neuroimage.2019.116064);
  arXiv: [1905.05953](https://arxiv.org/abs/1905.05953))

## Why `bfr+dipole`

AutoQSM is a **single-step** V-Net that goes straight from the **total field map** to susceptibility
in one learned pass — it performs **no brain extraction** and **no separate background-field
removal** (that is the paper's headline result). So it consumes the **total field** and produces
**susceptibility**, i.e. the `bfr+dipole` span, not the `dipole`-only stage. The `mask` mounted for
this span is unused: AutoQSM operates on the whole head.

## Units

QSM-CI's `totalfield.nii.gz` is an unwrapped field map already **in ppm** (normalized by B0). This is
exactly the scale AutoQSM's `x_input` expects: the repo's `test_data/0.mat` `x_input` is a dense
whole-head field map with values ≈ [−0.9, 0.5] and std ≈ 0.11 — the scale of a 3T total field in ppm,
and dense (no zero background) as expected for a method that skips brain extraction. So the field is
fed through **unchanged**. The V-Net's final activation is `tanh`, so its output susceptibility is in
ppm as well and is written out unchanged. No Hz/rad/ppm rescaling is performed. The output preserves
the input grid, voxel size, and affine.

## How QSM-CI runs it

```bash
python predict.py /input/totalfield.nii.gz /output/chimap.nii.gz
```

`predict.py` reuses AutoQSM's own network (`model.vnet`) and its patch-based sliding-window inference
(`util.data_predict`, which edge-pads to a multiple of `shift=24` and stitches 64³ → 32³ patches),
loading the pretrained weights `models/vnet/model_final_1.hdf5`. AutoQSM has no acquisition-parameter
inputs (no B0-direction / dipole-kernel term — orientation is baked into the trained weights), so
`run.sh` passes none. CPU inference is author-reported at ~55 s.

## Parameters

AutoQSM has no runtime tunables — it uses fixed pretrained weights.

## Building the image

The environment image bakes the legacy stack **and** the AutoQSM code + pretrained weights (~17 MB,
committed in-repo — not LFS), so the scoring run works fully offline (`--network none`). It must be
built and pushed before scoring works:

```bash
docker build -t ghcr.io/astewartau/qsm-ci/autoqsm:v1 algorithms/autoqsm
docker push  ghcr.io/astewartau/qsm-ci/autoqsm:v1
```

The submission's own `run.sh` + `predict.py` are mounted read-only at `/algo` at run time (not baked).

_Citations/DOIs are auto-generated best-effort references and should be verified._
