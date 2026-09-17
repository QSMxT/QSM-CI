"""pin_image: every submission's `image:` must reach Zenodo pinned to a digest.

A manifest that fails to pin is reported as "could not resolve its image to a digest" and skipped,
which leaves a `versions: {}` stub in the registry — the method is then unrunnable from a bare
`pip install qsm-ci` until the next release. That happened to decompose-qsmrs at v0.5.0 purely
because it documents its image with a trailing comment, so the real manifests are checked here too.
"""

import importlib.util
import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "publish_zenodo", ROOT / ".github" / "scripts" / "publish-zenodo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DIGEST = "sha256:" + "a" * 64


@pytest.fixture
def pz(monkeypatch):
    """The module with digest resolution stubbed — the network/docker is not under test here."""
    mod = _module()
    monkeypatch.setattr(mod, "image_digest", lambda ref: DIGEST)
    return mod


def test_plain_ref_is_pinned(pz):
    text, pinned = pz.pin_image("image: ghcr.io/x/y:v1\nrun: bash run.sh\n")
    assert pinned == f"ghcr.io/x/y@{DIGEST}"
    assert f"image: ghcr.io/x/y@{DIGEST}" in text


def test_trailing_comment_does_not_defeat_the_pin(pz):
    """`image: repo:tag   # why` must pin, and keep the comment."""
    src = "image: ghcr.io/x/qsmxt:v9.16.0   # the shared engine image\nrun: bash run.sh\n"
    text, pinned = pz.pin_image(src)
    assert pinned == f"ghcr.io/x/qsmxt@{DIGEST}"
    assert f"image: ghcr.io/x/qsmxt@{DIGEST}   # the shared engine image" in text
    assert yaml.safe_load(text)["image"] == f"ghcr.io/x/qsmxt@{DIGEST}"


def test_already_pinned_is_left_alone(pz):
    src = f"image: ghcr.io/x/y@{DIGEST}\n"
    text, pinned = pz.pin_image(src)
    assert (text, pinned) == (src, f"ghcr.io/x/y@{DIGEST}")


def test_no_image_key_yields_no_pin(pz):
    text, pinned = pz.pin_image("run: bash run.sh\n")
    assert pinned is None


def test_no_pin_when_the_digest_cannot_be_resolved(monkeypatch):
    mod = _module()
    monkeypatch.setattr(mod, "image_digest", lambda ref: None)
    assert mod.pin_image("image: ghcr.io/x/y:v1\n")[1] is None


def test_every_submission_manifest_can_be_pinned(pz):
    """No real manifest may be shaped so that pin_image can't find its image."""
    unpinnable = []
    for manifest in sorted((ROOT / "algorithms").glob("*/algorithm.yml")):
        text = manifest.read_text()
        if not yaml.safe_load(text).get("image"):
            continue  # a submission may legitimately carry no image (built from a Dockerfile)
        if pz.pin_image(text)[1] is None:
            unpinnable.append(manifest.parent.name)
    assert not unpinnable, f"pin_image cannot resolve the image line of: {unpinnable}"
