# Python originals (scikit-image best path, DIPY Gibbs removal and MP-PCA)

`ghcr.io/astewartau/qsm-ci/py-originals:v1`
(`sha256:7654140b9e7ff00552590d945db9b8d52c526fd01b8e36d5e1ad524b02b510ed`): Python 3.12 with
scikit-image 0.26.0 and DIPY 1.12.1, every wheel hash-locked (`requirements.lock`). Not QSM-CI
stages: they run as fixture runs ([`fidelity/cpp-py`](../../fidelity/cpp-py/README.md)), never
scored.

| script | calls | QSM.rs port |
|---|---|---|
| `bestpath.py PHASE OUT [--mask M] [--seed N]` | `skimage.restoration.unwrap_phase` (3-D, `wrap_around=False`, `rng=N`) | `unwrap/bestpath.rs` |
| `gibbs.py IN OUT` | `dipy.denoise.gibbs.gibbs_removal` (defaults: `slice_axis=2`, `n_points=3`) | `utils/gibbs.rs` |
| `mppca.py IN OUT [--mask M] [--patch-radius R]` | `dipy.denoise.localpca.mppca` (`pca_method='eig'`, radius 2) | `utils/denoise.rs` |

- **Versions:** scikit-image 0.26.0 is what `bestpath.rs` cites. QSM.rs cites no DIPY version;
  1.12.1 was current when the Gibbs and MP-PCA ports were written (2026-08-13) and is the latest.
- **Threads:** OpenMP/OpenBLAS/MKL 1 (image `ENV`); Gibbs runs in one process.
- **Licence:** scikit-image and DIPY are BSD-3-Clause (as are NumPy and SciPy; nibabel is MIT).
  Redistribution in a public image is allowed.
