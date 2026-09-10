"""The CLI fails cleanly — a message and a non-zero exit — never a raw traceback.

Four regressions pinned here (GitHub #191, #194, #195/#224, #197):

* `qsm-ci new --stage foo` / `--lang cobol` used to die with KeyError from the template tables;
  the flag path must validate against the known stages/languages and list the valid values.
* a run.sh that exits non-zero surfaced as subprocess.CalledProcessError, and a non-NIfTI --truth
  (or a method that wrote garbage) as nibabel's ImageFileError; both must become a message.
* `docker pull` output was swallowed and every failure blamed the author ("Build and push the image
  first") — the real registry error must be shown and not-found / auth / rate-limit told apart; the
  apptainer no-image message must not tell people to build with `--runner docker` in a module whose
  runner never builds.
* `qsm-ci submit` auto-confirmed every prompt when stdin was not a TTY, so a scripted call would
  branch, commit, push and open a PR unasked; it must require --yes there, and must stop when
  `git checkout` fails rather than committing on whatever branch it happens to be on.
"""
import argparse
import os
import stat
import subprocess
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from qsm_ci import cli, containers, runner, scaffold, submit
from qsm_ci.stages import STAGES
from qsm_ci.templates import LANGS

ROOT = Path(__file__).resolve().parent.parent
METHODS = ROOT / "tests" / "methods"
SHAPE = (6, 6, 6)


def _nii(path: Path, value=None, seed=0) -> str:
    rng = np.random.default_rng(seed)
    data = (np.full(SHAPE, value, "float32") if value is not None
            else rng.normal(size=SHAPE).astype("float32"))
    nib.save(nib.Nifti1Image(data, np.diag([1.0, 1.0, 1.0, 1.0])), str(path))
    return str(path)


# ----------------------------------------------------------------------------- #191: qsm-ci new


@pytest.mark.parametrize("flag,bad,valid", [
    ("--stage", "foo", list(STAGES)),
    ("--lang", "cobol", list(LANGS)),
])
def test_new_rejects_unknown_stage_or_lang_with_the_valid_values(tmp_path, monkeypatch, capsys, flag, bad, valid):
    monkeypatch.chdir(tmp_path)
    argv = ["new", "--name", "My Method", "--stage", "dipole", "--lang", "python", flag, bad]
    with pytest.raises(SystemExit) as exc:  # argparse-style usage error: message + exit 2, no traceback
        cli.main(argv)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert bad in err
    for v in valid:
        assert v in err, f"{flag} error must list the valid value {v!r}"
    assert not (tmp_path / "my-method").exists()  # nothing was scaffolded


def test_run_new_validates_flags_before_touching_the_disk(tmp_path):
    """run_new itself (not just the argparse layer) refuses an unknown stage/lang — a SystemExit
    that names the valid values, not a KeyError from the template tables."""
    for field, bad, valid in (("stage", "foo", STAGES), ("lang", "cobol", LANGS)):
        ns = argparse.Namespace(name="My Method", stage="dipole", lang="python", slug=None,
                                image=None, dir=str(tmp_path), force=False)
        setattr(ns, field, bad)
        with pytest.raises(SystemExit) as exc:
            scaffold.run_new(ns)
        msg = str(exc.value)
        assert bad in msg and all(v in msg for v in valid)
    assert not any(tmp_path.iterdir())


def test_new_still_scaffolds_a_valid_stage_and_lang(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["new", "--name", "My Method", "--stage", "bfr", "--lang", "julia"]) == 0
    assert (tmp_path / "my-method" / "algorithm.yml").exists()


# ------------------------------------------------------------- #194: failing run.sh / bad NIfTI


def _bfr_argv(tmp_path: Path, slug: str, extra=()):
    return [slug, "--runner", "local",
            "--totalfield", _nii(tmp_path / "tf.nii.gz"),
            "--mask", _nii(tmp_path / "mask.nii.gz", value=1.0),
            "-o", str(tmp_path / "out.nii.gz"), *extra]


def test_failing_run_sh_is_a_message_and_a_nonzero_exit_not_a_traceback(tmp_path, monkeypatch):
    monkeypatch.setenv("QSMCI_ALGORITHMS", str(METHODS))
    monkeypatch.chdir(tmp_path)
    msgs = []
    rc = runner.run_command(_bfr_argv(tmp_path, "fail-bfr"), log=msgs.append)  # run.sh does `exit 3`
    assert rc != 0
    text = "\n".join(msgs)
    assert "exit" in text.lower() and "3" in text, text          # the exit status is reported
    assert "stderr" in text.lower() or "output above" in text.lower(), text  # where to look
    assert not (tmp_path / "out.nii.gz").exists()


def test_failing_run_sh_through_main_exits_nonzero_cleanly(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("QSMCI_ALGORITHMS", str(METHODS))
    monkeypatch.chdir(tmp_path)
    rc = cli.main(["run", *_bfr_argv(tmp_path, "fail-bfr")])  # must not raise CalledProcessError
    assert rc != 0
    out = capsys.readouterr()
    assert "Traceback" not in out.out + out.err


def test_non_nifti_truth_is_a_clear_message(tmp_path, monkeypatch):
    monkeypatch.setenv("QSMCI_ALGORITHMS", str(METHODS))
    monkeypatch.chdir(tmp_path)
    bad = tmp_path / "truth.txt"
    bad.write_text("not a nifti\n")
    with pytest.raises(SystemExit) as exc:
        runner.run_command(_bfr_argv(tmp_path, "cp-bfr", ["--truth", str(bad)]), log=lambda *_: None)
    msg = str(exc.value)
    assert "--truth" in msg and "NIfTI" in msg and str(bad) in msg, msg
    assert not (tmp_path / "out.nii.gz").exists()  # rejected BEFORE the (possibly long) run


def test_non_nifti_seg_is_a_clear_message(tmp_path, monkeypatch):
    monkeypatch.setenv("QSMCI_ALGORITHMS", str(METHODS))
    monkeypatch.chdir(tmp_path)
    bad = tmp_path / "seg.nii.gz"
    bad.write_bytes(b"not gzip, not nifti")
    truth = _nii(tmp_path / "truth.nii.gz")
    with pytest.raises(SystemExit) as exc:
        runner.run_command(_bfr_argv(tmp_path, "cp-bfr", ["--truth", truth, "--seg", str(bad)]),
                           log=lambda *_: None)
    assert "--seg" in str(exc.value) and "NIfTI" in str(exc.value)
    assert not (tmp_path / "out.nii.gz").exists()


def test_valid_truth_still_scores(tmp_path, monkeypatch):
    """The pre-flight check must not break the happy path: cp-bfr copies its input, so scoring
    against that same input gives correlation 1."""
    monkeypatch.setenv("QSMCI_ALGORITHMS", str(METHODS))
    monkeypatch.chdir(tmp_path)
    msgs = []
    argv = _bfr_argv(tmp_path, "cp-bfr", ["--truth", str(tmp_path / "tf.nii.gz")])
    assert runner.run_command(argv, log=msgs.append) == 0
    assert (tmp_path / "out.nii.gz").exists()
    assert any("correlation" in m and "1.0000" in m for m in msgs), msgs


def test_non_nifti_output_is_a_clear_message(tmp_path):
    """A method that writes something nibabel can't read: the scorer names the offending file."""
    recon = tmp_path / "localfield.nii.gz"
    recon.write_bytes(b"garbage")
    truth = _nii(tmp_path / "truth.nii.gz")
    mask = _nii(tmp_path / "mask.nii.gz", value=1.0)
    with pytest.raises(SystemExit) as exc:
        runner._score(recon, "localfield", Path(truth), Path(mask), None)
    msg = str(exc.value)
    assert "NIfTI" in msg and str(recon) in msg and "Traceback" not in msg


# ----------------------------------------------------- #195 / #224: docker pull output + wording


def _fake_engine(tmp_path: Path, pull_stderr: str, pull_rc: int, inspect_rc: int) -> str:
    """A stand-in docker/podman: `pull` prints progress on stdout + the given stderr and exits
    pull_rc; `image inspect` exits inspect_rc (0 = a local copy is cached)."""
    script = tmp_path / "fake-engine"
    script.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = pull ]; then\n'
        '  echo "layer 1/3: downloading"\n'
        f'  printf %s "{pull_stderr}" >&2\n'
        f"  exit {pull_rc}\n"
        "fi\n"
        f'if [ "$1" = image ]; then exit {inspect_rc}; fi\n'
        "exit 99\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_pull_streams_progress_and_succeeds(tmp_path, capfd):
    engine = _fake_engine(tmp_path, "", pull_rc=0, inspect_rc=1)
    msgs = []
    assert containers._build_oci({"image": "ghcr.io/x/y:v1"}, engine, msgs.append) == "ghcr.io/x/y:v1"
    assert "layer 1/3: downloading" in capfd.readouterr().out  # the engine's progress reaches the user


@pytest.mark.parametrize("stderr,expect,reject", [
    ("Error response from daemon: manifest unknown", ["not found", "image:"], ["Build and push"]),
    ("Error response from daemon: manifest for ghcr.io/x/y:v1 not found: manifest unknown", ["not found"], ["Build and push"]),
    ("Error response from daemon: Head https://ghcr.io/v2/x/y/manifests/v1: unauthorized", ["login"], ["Build and push"]),
    ("Error response from daemon: toomanyrequests: You have reached your pull rate limit.", ["rate limit"], ["Build and push", "login"]),
    ("Error response from daemon: Get https://ghcr.io/v2/: dial tcp: lookup ghcr.io: no such host", ["network"], ["Build and push"]),
])
def test_pull_failure_shows_the_registry_error_and_classifies_it(tmp_path, capfd, stderr, expect, reject):
    engine = _fake_engine(tmp_path, stderr, pull_rc=1, inspect_rc=1)
    with pytest.raises(SystemExit) as exc:
        containers._build_oci({"image": "ghcr.io/x/y:v1"}, engine, lambda *_: None)
    msg = str(exc.value)
    assert "ghcr.io/x/y:v1" in msg
    for word in expect:
        assert word.lower() in msg.lower(), (word, msg)
    for word in reject:
        assert word.lower() not in msg.lower(), (word, msg)
    # the engine's real stderr is not swallowed — it reaches the user's terminal
    assert stderr.split(":")[-1].strip() in capfd.readouterr().err


def test_pull_failure_falls_back_to_a_cached_copy_with_the_reason(tmp_path, capfd):
    engine = _fake_engine(tmp_path, "dial tcp: no such host", pull_rc=1, inspect_rc=0)
    msgs = []
    assert containers._build_oci({"image": "ghcr.io/x/y:v1"}, engine, msgs.append) == "ghcr.io/x/y:v1"
    assert any("cached" in m for m in msgs)


def test_rate_limit_is_distinguished_from_not_found_even_when_the_registry_says_denied(tmp_path):
    """Docker Hub's rate-limit text also says "denied"; it must not be read as auth or not-found."""
    stderr = "toomanyrequests: You have reached your pull rate limit. Access denied."
    engine = _fake_engine(tmp_path, stderr, pull_rc=1, inspect_rc=1)
    with pytest.raises(SystemExit) as exc:
        containers._build_oci({"image": "x/y:v1"}, engine, lambda *_: None)
    assert "rate limit" in str(exc.value).lower()


def test_apptainer_no_image_message_does_not_claim_the_runner_builds(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM scratch\n")
    with pytest.raises(SystemExit) as exc:
        containers._apptainer_image({"dir": tmp_path})
    msg = str(exc.value)
    assert "--runner docker" not in msg and "Build it first" not in msg
    assert "never builds" in msg and "image:" in msg


# ------------------------------------------------------------------- #197: submit needs --yes


class _FakeGit:
    """Records every git invocation; `fail` names subcommands that return non-zero."""

    def __init__(self, fail=()):
        self.calls = []
        self.fail = set(fail)

    def __call__(self, *args, **kw):
        self.calls.append(args)
        rc = 1 if args[0] in self.fail else 0
        stdout = ""
        if args[:2] == ("remote", "get-url"):
            stdout = "https://github.com/me/QSM-CI\n"
        if args[:2] == ("rev-parse", "--verify"):
            rc = 1  # the submit branch does not exist yet
        return subprocess.CompletedProcess(["git", *args], rc, stdout=stdout, stderr="")

    def subcommands(self):
        return [c[0] for c in self.calls]


@pytest.fixture
def submit_repo(tmp_path, monkeypatch):
    (tmp_path / "algorithms" / "my-method").mkdir(parents=True)
    (tmp_path / "algorithms" / "my-method" / "algorithm.yml").write_text("stage: dipole\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(submit, "_has", lambda cmd: cmd == "git")  # git yes, gh no
    monkeypatch.setattr(submit, "_interactive", lambda: False)
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("submit must not prompt when not a TTY"))
    monkeypatch.setattr(submit.subprocess, "run",
                        lambda *a, **k: pytest.fail(f"unexpected subprocess: {a}"))
    return tmp_path


def _args(yes=False):
    return argparse.Namespace(slug="my-method", yes=yes)


def test_submit_parser_has_a_yes_flag():
    p = cli.build_parser()
    assert p.parse_args(["submit", "x", "--yes"]).yes is True
    assert p.parse_args(["submit", "x", "-y"]).yes is True
    assert p.parse_args(["submit", "x"]).yes is False
    assert "--yes" in p._subparsers._group_actions[0].choices["submit"].format_help()


def test_submit_without_a_tty_aborts_before_doing_anything(submit_repo, monkeypatch, capsys):
    git = _FakeGit()
    monkeypatch.setattr(submit, "_git", git)
    rc = submit.run_submit(_args())
    assert rc != 0
    out = capsys.readouterr()
    assert "--yes" in out.out + out.err
    assert not {"checkout", "add", "commit", "push"} & set(git.subcommands()), git.calls


def test_submit_without_a_tty_proceeds_with_yes(submit_repo, monkeypatch):
    git = _FakeGit()
    monkeypatch.setattr(submit, "_git", git)
    assert submit.run_submit(_args(yes=True)) == 0
    subs = git.subcommands()
    assert ("checkout", "-b", "submit/my-method") in git.calls
    assert "add" in subs and "commit" in subs and "push" in subs
    assert ("push", "-u", "origin", "submit/my-method") in git.calls


def test_submit_stops_when_checkout_fails(submit_repo, monkeypatch, capsys):
    git = _FakeGit(fail={"checkout"})
    monkeypatch.setattr(submit, "_git", git)
    assert submit.run_submit(_args(yes=True)) != 0
    subs = git.subcommands()
    assert "checkout" in subs
    assert not {"add", "commit", "push"} & set(subs), git.calls
    assert "checkout" in (capsys.readouterr().out.lower())


def test_confirm_never_silently_answers_yes_without_a_tty(monkeypatch):
    monkeypatch.setattr(submit, "_interactive", lambda: False)
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("must not prompt"))
    with pytest.raises(SystemExit):
        submit._confirm("  Push?")
    assert submit._confirm("  Push?", yes=True) is True
