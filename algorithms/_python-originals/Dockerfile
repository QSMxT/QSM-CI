# Python originals of QSM.rs's ports (QSMxT/QSM-CI#302), in one pinned environment:
#   - scikit-image 0.26.0  `skimage.restoration.unwrap_phase`, the authors' 3-D best-path C code
#     (unwrap_3d_ljmu.c) that qsm_core::unwrap::bestpath follows (QSM.rs cites 0.26.0);
#   - DIPY 1.12.1          `dipy.denoise.gibbs.gibbs_removal` and `dipy.denoise.localpca.mppca`,
#     which qsm_core::utils::gibbs and ::denoise port. QSM.rs cites no DIPY version; 1.12.1 was the
#     release current when those ports were written (2026-08-13) and is still the latest.
# Python 3.12 (official slim image, by digest) and an exact, hash-checked closure of wheels
# (requirements.lock). scikit-image and DIPY are BSD-3-Clause. The call scripts (bestpath.py,
# gibbs.py, mppca.py) are mounted at run time, never baked.
#
#   podman build -t ghcr.io/astewartau/qsm-ci/py-originals:v1 algorithms/_python-originals
#   podman push  ghcr.io/astewartau/qsm-ci/py-originals:v1
FROM docker.io/library/python:3.12-slim-bookworm@sha256:72c1d56207fb14ca388f9b3855ac0e55ab557703928180ec40aa9d4c4f5d5f80

COPY requirements.lock /opt/py-originals/requirements.lock
RUN pip install --no-cache-dir --no-deps --require-hashes -r /opt/py-originals/requirements.lock \
    && python -c "import skimage, dipy, nibabel, numpy; print(skimage.__version__, dipy.__version__, nibabel.__version__, numpy.__version__)"

# Single-threaded BLAS/OpenMP: part of the fidelity record (fidelity/cpp-py/README.md).
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/mpl
