# LPCNN

Learned Proximal Convolutional Neural Network — a learned-proximal, unrolled deep network
for the QSM dipole-inversion problem.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [LPCNN](https://github.com/Sulam-Group/LPCNN) — PyTorch, **CPU-only** (`--no_cuda`)
- **Reference:** Lai K-W., Aggarwal M., van Zijl P., Li X., Sulam J. (2020). *Learned Proximal Networks for Quantitative Susceptibility Mapping.* MICCAI 2020, LNCS 12262, Springer. (DOI: [10.1007/978-3-030-59713-9_13](https://doi.org/10.1007/978-3-030-59713-9_13); arXiv:[2008.05024](https://arxiv.org/abs/2008.05024))

## Why `dipole`

LPCNN solves the ill-posed dipole deconvolution: it maps the **local (tissue) field** to
**susceptibility** by unrolling proximal gradient descent (`iter_num = 3` in
`lib/model/lpcnn/lpcnn.py`). Each iteration applies a physics data-consistency step using the
dipole kernel `D` in k-space, followed by a learned 3D-CNN proximal operator. It consumes
`localfield` + `mask` + `params` and produces `chimap`, i.e. the `dipole` stage — no
background-field removal is done.

We run it in **single-orientation** mode (`--number 1`), the general single-input QSM setting
(LPCNN also supports 2–3 orientations, not used here).

## Units

QSM-CI's `localfield` is in **ppm** (normalized by B0). LPCNN's `inference.py` reads its phase
input and divides by `tesla * gamma` (`gamma = 42.57747892` MHz/T) — its dataset "phase" files
are the local field in **Hz**. So `run.sh`/`recon.py` write the phase file the model reads in
Hz: `Hz = ppm · tesla · gamma`. The model's internal `/(tesla·gamma)` then recovers the ppm
field the physics operator and the pretrained (ppm) `gt_mean`/`gt_std` expect. The output is
denormalized back to ppm and written to `chimap.nii.gz`.

## Dipole kernel generation

The physics operator needs a dipole kernel encoding the **B0 direction** and matrix size; only
demo kernels ship in the repo. `recon.py` generates it from `params.json` (`B0_dir`,
`voxel_size`, and the volume matrix size) in the exact convention the model consumes
(`np.load` of a `.npy`, multiplied against the ortho FFT of the field with DC at the array
corner):

```
D = 1/3 − (k · B0)² / |k|²,   k from np.fft.fftfreq(n, d=voxel),   D[0,0,0] = 0
```

built in `(x, y, z)` order. This was verified against the shipped `.mat` kernels (after
`data/to_numpy.py`'s `swapaxes(0,1)`): `max|D_shipped − D_generated| ≈ 9e-8` on a demo case,
and an end-to-end run against a COSMOS target reproduces a physically-correct ppm map
(single-orientation correlation ≈ 0.86).

## How QSM-CI runs it

```bash
# recon.py builds phase.nii.gz (Hz), dipole.npy, and the .txt file-lists, then:
python LPCNN/inference.py --number 1 --tesla <3|7> --no_cuda \
  --phase_file phase_data.txt --dipole_file dipole_data.txt --mask_file mask_data.txt \
  --resume_file checkpoints/lpcnn_test_Bmodel.pkl
```

`--tesla` is snapped from `params.json` `B0` / `QSMCI_B0` to the nearer supported field (3 or
7); the weights are trained at 7T. Inputs are handed to `inference.py` as `.txt` file-lists,
which `run.sh` builds. The `~5 MB` checkpoints (`lpcnn_test_Bmodel.pkl`, `_Emodel.pkl`) and the
small normalization stat `.npy` files are **committed in the LPCNN repo** and baked into the
image, so the scoring run works fully offline (`--network none`). We use **Bmodel** by default
(override with `LPCNN_RESUME` to pick `_Emodel.pkl`).

## Parameters

LPCNN has no runtime tunables here — fixed pretrained weights. The acquisition-derived inputs
are the B0 direction and voxel size (from `params.json` / env vars), used to build the dipole
kernel, plus the field strength (used to pick `--tesla`).

## Building the image

The QSM-CI scorer builds this folder's `Dockerfile` at score time (build phase, network ON),
then runs `bash run.sh` with the network OFF. To build/push manually:

```bash
docker build -t ghcr.io/astewartau/qsm-ci/lpcnn:v1 algorithms/lpcnn
docker push  ghcr.io/astewartau/qsm-ci/lpcnn:v1
```

The Dockerfile uses the **modernized 2025 LPCNN code path** (tested Python 3.13 / PyTorch 2.9),
CPU-only PyTorch, not the old conda `environment.yml`.

_Citations/DOIs are auto-generated best-effort references and should be verified._
