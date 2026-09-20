"""`-o` gets the format it asked for, and a mislabelled NIfTI is read by content, not by name.

Every submission writes `<artifact>.nii.gz` — the contract requires it. The CLI then copied those
bytes verbatim to whatever `-o` named, so `qsm-ci run hd-bet-qsmci -o mask.nii` handed back valid
gzip data wearing a `.nii` name. Nothing stage-specific: the copy is in the generic output loop, so
every single-output stage did it.

Worse, it was a closed loop. Feeding that file back in, `_place_input` trusted the `.nii` suffix and
gzipped it a SECOND time; the container gunzipped once and parsed the inner gzip header as a NIfTI
one, reporting `sizeof_hdr=559903` — which is the gzip magic `1f 8b 08 00` read as a little-endian
int32. So the tool authored a file it then refused to read.

Both sides now decide by content: `place_nifti(..., gzipped=)` converts as needed, `wants_gzip()`
reads the requested name, and only a plain `.nii` asks for uncompressed.
"""
import gzip
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from qsm_ci import runner
from qsm_ci.params import _is_gzip, place_nifti, wants_gzip

ROOT = Path(__file__).resolve().parent.parent
METHODS = ROOT / "tests" / "methods"
SHAPE = (5, 5, 5)


def _nii(path: Path, seed=0) -> Path:
    """A real NIfTI. nibabel picks its format from the suffix, so `.nii` lands uncompressed."""
    rng = np.random.default_rng(seed)
    nib.save(nib.Nifti1Image(rng.normal(size=SHAPE).astype("float32"),
                             np.diag([1.0, 1.0, 1.0, 1.0])), str(path))
    return path


def _gzip_named_nii(path: Path, seed=0) -> Path:
    """The file that started this: valid gzipped NIfTI, misleading `.nii` name."""
    tmp = path.parent / f"{path.stem}.real.nii.gz"
    _nii(tmp, seed=seed)
    path.write_bytes(tmp.read_bytes())
    tmp.unlink()
    return path


def _data(path: Path) -> np.ndarray:
    """Load by CONTENT — nibabel picks its reader from the suffix too, so it cannot open the
    mislabelled file the tool used to produce. Decompress first when the bytes say gzip."""
    raw = gzip.decompress(path.read_bytes()) if _is_gzip(path) else path.read_bytes()
    probe = path.parent / f"{path.name}.probe.nii"   # a name nibabel will accept, whatever `path` is
    probe.write_bytes(raw)
    return nib.load(str(probe)).get_fdata()


# ----------------------------------------------------------------------- the converter itself

def test_is_gzip_reads_magic_bytes_not_the_name(tmp_path):
    assert _is_gzip(_nii(tmp_path / "a.nii.gz")) is True
    assert _is_gzip(_nii(tmp_path / "b.nii")) is False
    assert _is_gzip(_gzip_named_nii(tmp_path / "liar.nii")) is True   # the hd-bet output
    assert _is_gzip(tmp_path / "does-not-exist.nii") is False


@pytest.mark.parametrize("src_name", ["src.nii", "src.nii.gz", "liar.nii"])
@pytest.mark.parametrize("gzipped", [True, False])
def test_place_nifti_converts_from_any_source(tmp_path, src_name, gzipped):
    """All six combinations: the destination gets the format asked for, and the data survives."""
    src = (_gzip_named_nii(tmp_path / src_name) if src_name == "liar.nii"
           else _nii(tmp_path / src_name))
    expected = _data(src)

    dest = tmp_path / "out" / "placed.bin"
    place_nifti(src, dest, gzipped=gzipped)

    assert _is_gzip(dest) is gzipped
    np.testing.assert_allclose(_data(dest), expected)


@pytest.mark.parametrize("name,gz", [
    ("mask.nii", False), ("mask.nii.gz", True), ("out/", True), ("mask", True),
])
def test_wants_gzip_only_a_plain_nii_asks_for_uncompressed(name, gz):
    assert wants_gzip(name) is gz


# ------------------------------------------------------------------- end to end through the CLI

def _run(tmp_path, monkeypatch, totalfield, out):
    monkeypatch.setenv("QSMCI_ALGORITHMS", str(METHODS))
    monkeypatch.chdir(tmp_path)
    mask = _nii(tmp_path / "mask.nii.gz", seed=1)
    rc = runner.run_command(["cp-bfr", "--runner", "local",
                             "--totalfield", str(totalfield), "--mask", str(mask),
                             "-o", str(out)], log=lambda *_: None)
    assert rc == 0, "cp-bfr should succeed"
    return out


def test_dash_o_nii_writes_an_uncompressed_nifti(tmp_path, monkeypatch):
    """The reported bug: `-o x.nii` used to yield gzip bytes under a .nii name."""
    tf = _nii(tmp_path / "tf.nii.gz")
    out = _run(tmp_path, monkeypatch, tf, tmp_path / "out.nii")
    assert not _is_gzip(out), "-o *.nii must not be gzip-compressed"
    np.testing.assert_allclose(_data(out), _data(tf))


def test_dash_o_nii_gz_stays_compressed(tmp_path, monkeypatch):
    tf = _nii(tmp_path / "tf.nii.gz")
    out = _run(tmp_path, monkeypatch, tf, tmp_path / "out.nii.gz")
    assert _is_gzip(out)
    np.testing.assert_allclose(_data(out), _data(tf))


def test_output_of_one_run_is_valid_input_to_the_next(tmp_path, monkeypatch):
    """The closed loop, end to end: `-o x.nii` then feed x.nii straight back in.

    This is the hd-bet mask → next-stage --mask path. It used to double-gzip and die inside the
    container with `sizeof_hdr=559903`.
    """
    tf = _nii(tmp_path / "tf.nii.gz")
    first = _run(tmp_path, monkeypatch, tf, tmp_path / "step1.nii")
    assert not _is_gzip(first)

    second = _run(tmp_path, monkeypatch, first, tmp_path / "step2.nii.gz")
    # cp-bfr copies its input through, so surviving the round trip means the data is intact
    np.testing.assert_allclose(_data(second), _data(tf))


def test_a_gzip_file_misnamed_nii_is_still_read(tmp_path, monkeypatch):
    """Files that older versions already wrote to disk must keep working."""
    liar = _gzip_named_nii(tmp_path / "mask2.nii")
    out = _run(tmp_path, monkeypatch, liar, tmp_path / "out.nii.gz")
    np.testing.assert_allclose(_data(out), _data(liar))
