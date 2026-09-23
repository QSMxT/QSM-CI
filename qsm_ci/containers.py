"""Container execution: pick a runner, resolve the image, and run a submission's ``run.sh``.

Runners are docker/podman (OCI engines), apptainer, or ``local`` (run.sh on the host). CI never
builds containers — every submission publishes a prebuilt ``image:`` and we only pull/run it. A
folder Dockerfile is the build recipe (used out-of-band to produce that image), never built here.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from .resources import _ResourceSampler, _ProcResourceSampler
from .stages import ARTIFACT_FILE

RUNNERS = ("docker", "podman", "apptainer", "local")
_OCI_ENGINES = ("docker", "podman")  # daemonless podman is CLI-compatible with docker

# CONTRACT.md: "Default 2 h wall-clock; exceeding it is a DNF." Enforced here, per RUN, rather than
# left to the GitHub job timeout — which kills the whole shard, so the other runs sharing it get no
# DNF rows at all, and leaves the container alive on a self-hosted box (the workflows' reaper step
# exists because of exactly that).
DEFAULT_TIMEOUT_S = 7200.0
# Grace between "the run is over time" and the container actually being gone. `docker kill` is
# asynchronous and a MATLAB/CUDA image can take a few seconds to unwind.
_KILL_GRACE_S = 30.0


class RunTimeout(RuntimeError):
    """A submission exceeded its wall-clock budget; its container has been killed."""


def timeout_s(override_minutes: "float | None" = None) -> "float | None":
    """Wall-clock budget for one run, in seconds, or None when disabled.

    Precedence: an explicit per-method override (`timeout_minutes:` in algorithm.yml, or the CLI's
    ``--timeout``) beats ``$QSMCI_TIMEOUT`` (seconds) beats the 2 h contract default. Either source
    may be ``0`` to disable the cap — useful when a human is driving a long run by hand and the
    shell is the supervisor.
    """
    if override_minutes is not None:
        return None if override_minutes <= 0 else float(override_minutes) * 60.0
    raw = os.environ.get("QSMCI_TIMEOUT", "").strip()
    if not raw:
        return DEFAULT_TIMEOUT_S
    try:
        v = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_S
    return None if v <= 0 else v


def _human(seconds: float) -> str:
    if seconds >= 3600:
        return f"{seconds / 3600:.1f} h"
    return f"{seconds / 60:.1f} min" if seconds >= 60 else f"{seconds:.0f}s"


def _timeout_msg(limit: float) -> str:
    return (f"timed out after {_human(limit)} — the CONTRACT wall-clock limit; raise it with "
            f"`timeout_minutes:` in algorithm.yml or $QSMCI_TIMEOUT")


def _gpu_flags(runner: str) -> list[str]:
    """GPU-passthrough flags for the given runner, or [] when GPU is not requested.

    Opt-in via the ``QSMCI_GPU`` env var (truthy: 1/true/yes). Default OFF, so CI — which runs on
    CPU-only hosts and never sets it — is byte-identical to before. On a GPU host (e.g. an HPC GPU
    node) export ``QSMCI_GPU=1`` and the container gets the host GPUs; images whose torch is a CUDA
    build then use them, while CPU-only hosts (or ``QSMCI_FORCE_CPU=1`` in run.sh) fall back to CPU.
    """
    if os.environ.get("QSMCI_GPU", "").strip().lower() not in ("1", "true", "yes", "on"):
        return []
    if runner == "docker":
        return ["--gpus", "all"]
    if runner == "podman":
        return ["--device", "nvidia.com/gpu=all"]
    if runner == "apptainer":
        return ["--nv"]
    return []


def _have(binary: str) -> bool:
    return shutil.which(binary) is not None


# A wedged docker daemon makes `docker version`/`docker info` block forever. These probes only ever
# inform a choice we have a safe default for, so cap them rather than hanging the whole CLI.
_PROBE_TIMEOUT = 10.0


def check_runner(runner: str) -> bool:
    """Is the tooling for this runner available?"""
    if runner == "local":
        return True
    if runner == "docker":  # also confirm the daemon answers
        try:
            return subprocess.run(["docker", "version"], capture_output=True,
                                  timeout=_PROBE_TIMEOUT).returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    return _have(runner)


@lru_cache(maxsize=None)
def _docker_is_rootless() -> bool:
    """Is this docker CLI talking to a ROOTLESS daemon?

    A rootless daemon runs inside a user namespace in which the invoking host user is mapped to uid
    0, so the bind-mounted files you own look root-owned from inside the container. Passing
    ``--user <host uid>:<host gid>`` there selects a uid that is *unmapped* inside that namespace
    and every write to /output fails with EACCES. Under a root daemon the opposite holds: without
    ``--user`` the container writes root-owned files into your bind mount. So the flag is right for
    one and wrong for the other, and we have to ask which daemon this is.

    Unknown (no docker, probe timed out, old daemon without SecurityOptions) is reported as *not*
    rootless — the historical behaviour, and the common case."""
    try:
        r = subprocess.run(["docker", "info", "-f", "{{join .SecurityOptions \",\"}}"],
                           capture_output=True, text=True, timeout=_PROBE_TIMEOUT)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0 and "rootless" in r.stdout


def _user_args(runner: str) -> list[str]:
    """How to map the invoking user into the container, so /output comes back owned by them.

    ``QSMCI_CONTAINER_USER`` overrides the guess below: ``off`` (or ``none``/``false``/``no``) drops
    the mapping entirely and lets the engine decide; any other value is passed through verbatim as
    the ``--user`` argument (e.g. ``1000:1000``, ``root``)."""
    override = os.environ.get("QSMCI_CONTAINER_USER", "").strip()
    if override:
        if override.lower() in ("off", "none", "false", "no"):
            return []
        return ["--user", override]
    if runner == "podman":
        # rootless podman: keep-id maps your host uid inside, so files written to the /output
        # bind mount come back owned by you.
        return ["--userns=keep-id"]
    if not hasattr(os, "getuid"):
        return []  # Windows: no POSIX uid/gid to map, and os.getuid does not exist
    if _docker_is_rootless():
        return []  # you are already root inside the namespace; --user would break /output writes
    return ["--user", f"{os.getuid()}:{os.getgid()}"]  # root daemon: run as you directly


def _build_oci(algo: dict, engine: str, log) -> str:
    """docker/podman: PULL the submission's prebuilt image: and return its ref — never build.

    CI must not build containers. Every submission publishes a prebuilt ``image:``; a folder
    Dockerfile is only the build recipe (used out-of-band to produce that image), never built here.
    Pull the tag (streaming the engine's progress, so a multi-GB pull isn't minutes of silence);
    if the pull fails fall back to a locally cached copy; if neither is available, stop with the
    registry's actual error and a message that fits it — a missing tag, a private image / no login,
    a rate limit, or no network — rather than blaming the author for every failure (#195)."""
    tag = algo.get("image")
    if not tag:
        raise SystemExit(
            "algorithm.yml has no image:. Publish a prebuilt image (build and push it first) and set "
            "image: to its reference — the runner pulls images, it does not build containers.")
    log(f"↓ pulling {tag}")
    rc, err = _pull(engine, tag)
    if rc != 0:
        reason = _pull_failure_reason(err)
        # Offline / registry hiccup — fall back to a locally cached copy if one exists.
        if subprocess.run([engine, "image", "inspect", tag], capture_output=True).returncode == 0:
            log(f"  (pull failed: {reason.splitlines()[0]} — using locally cached {tag})")
            return tag
        raise SystemExit(f"could not pull {tag}: {reason}\n"
                         "  No local copy is cached. The runner only pulls prebuilt images — it never "
                         "builds one (a folder Dockerfile is just the recipe used to publish image:).")
    return tag


def _pull(engine: str, tag: str) -> "tuple[int, str]":
    """`<engine> pull <tag>`, streaming its output live and returning (exit code, stderr text).

    stdout is inherited (docker's layer progress goes there); stderr is teed line by line to our
    own stderr (podman's progress and every engine's error text go there) and kept so the failure
    can be classified. Nothing is swallowed."""
    proc = subprocess.Popen([engine, "pull", tag], stderr=subprocess.PIPE, text=True)
    lines = []
    assert proc.stderr is not None
    for line in proc.stderr:
        sys.stderr.write(line)
        sys.stderr.flush()
        lines.append(line)
    rc = proc.wait()
    return rc, "".join(lines)


# Registry error text → what actually went wrong. Order matters: Docker Hub's rate-limit message
# also says "denied", and Docker Hub's not-found message ("pull access denied … repository does
# not exist or may require 'docker login'") mentions both. First match wins.
_PULL_ERRORS = (
    ("rate limit", (r"toomanyrequests", r"rate limit", r"too many requests")),
    ("not found", (r"manifest unknown", r"not found", r"does not exist", r"name unknown",
                   r"invalid reference format", r"no such image")),
    ("auth", (r"unauthorized", r"denied", r"authentication required", r"login")),
    ("network", (r"no such host", r"dial tcp", r"connection refused", r"timeout", r"timed out",
                 r"network is unreachable", r"tls handshake", r"proxyconnect", r"i/o timeout")),
)


def _pull_failure_reason(stderr: str) -> str:
    """A one-paragraph explanation of a failed pull, from the engine's stderr."""
    text = stderr.strip()
    # the engine's own words — its last non-empty line is the summary ("Error response from daemon: …")
    said = next((l.strip() for l in reversed(text.splitlines()) if l.strip()), "no error output")
    kind = next((k for k, pats in _PULL_ERRORS
                 if any(re.search(p, text, re.IGNORECASE) for p in pats)), "other")
    if kind == "rate limit":
        return (f"the registry is rate-limiting pulls ({said}).\n"
                "  Wait and retry, or log in to the registry for a higher pull limit.")
    if kind == "not found":
        return (f"the registry reports the image as not found ({said}).\n"
                "  Check image: in algorithm.yml — a typo, a tag that was never pushed, or a private "
                "image you're not logged in to (`docker login <registry>`).")
    if kind == "auth":
        return (f"the registry refused access ({said}).\n"
                "  If the image is private, log in first (`docker login <registry>`); otherwise check "
                "image: in algorithm.yml.")
    if kind == "network":
        return (f"the registry could not be reached ({said}).\n"
                "  Check your network / proxy settings and retry.")
    return f"{said}"


def _sandbox_name(image: str) -> str:
    """Filesystem-safe directory name for a prebuilt apptainer sandbox of ``image``."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", image)


def _apptainer_image(algo: dict) -> str:
    """apptainer runs from a docker:// ref or a .sif — it can't build a Dockerfile itself.

    A published ``image:`` is used as-is (pulled & converted on the fly) exactly like the docker
    path does — a folder Dockerfile is only the build recipe, never built here. Only when no
    ``image:`` is set does a local Dockerfile become a hard error (apptainer can't build it).

    Prebuilt-image override ($QSMCI_SANDBOX_DIR): some hosts' unprivileged apptainer can't build a
    .sif from an OCI image on the fly because the squashfs step runs under proot and the kernel
    blocks its ptrace (seen on Bunya: ``mksquashfs … proot error: ptrace(TRACEME): Operation not
    permitted``). Two prebuilt forms sidestep it, both keyed by ``_sandbox_name(image)`` under
    QSMCI_SANDBOX_DIR: a ``.sif`` FILE (built once with ``apptainer build --fakeroot`` — compact, one
    inode, preferred) or a SANDBOX DIRECTORY (image unpacked, no squashfs — works without fakeroot
    but is inode-heavy). If either exists, exec it instead of pulling docker://. Absent the env var
    it's a no-op, so the default pull-and-convert path — and every existing caller — is unchanged."""
    img = algo.get("image")
    if img:
        if "://" in img or img.endswith(".sif") or os.path.exists(img):
            return img
        root = os.environ.get("QSMCI_SANDBOX_DIR")
        if root:
            base = os.path.join(root, _sandbox_name(img))
            if os.path.isfile(base + ".sif"):   # prefer the compact fakeroot-built .sif
                return base + ".sif"
            if os.path.isdir(base):             # fall back to an unpacked sandbox dir
                return base
        return f"docker://{img}"  # plain registry ref -> pull & convert on the fly
    # No image: at all. The runner never builds containers (with any --runner, #224): the folder
    # Dockerfile is only the recipe the author builds and pushes out-of-band.
    recipe = (" A Dockerfile is here, but the runner never builds it — build and push it yourself, then"
              if (algo["dir"] / "Dockerfile").exists() else " Publish a prebuilt image, then")
    raise SystemExit(
        f"algorithm.yml has no image: for apptainer to run.{recipe} set image: to its reference "
        "(a registry ref, docker://…, or a .sif).")


def _param_env(input_dir: Path) -> "dict[str, str]":
    """Layer B — expose params.json + config.json as ``QSMCI_*`` env vars so a run.sh needn't parse
    JSON (no `jq` needed): ``QSMCI_B0``, ``QSMCI_TE`` (space-separated echoes), ``QSMCI_TE0`` (first
    echo), ``QSMCI_B0_DIR``, ``QSMCI_VOXEL_SIZE``, and ``QSMCI_SET_<NAME>`` per --set override. The
    JSON files are still written (Layer A), so this is purely additive."""
    env: "dict[str, str]" = {}
    pj = input_dir / ARTIFACT_FILE["params"]
    if pj.exists():
        try:
            p = json.loads(pj.read_text())
        except Exception:  # noqa: BLE001
            p = {}
        te = p.get("TE") or []
        if te:
            env["QSMCI_TE"] = " ".join(str(t) for t in te)
            env["QSMCI_TE0"] = str(te[0])
        if p.get("B0") is not None:
            env["QSMCI_B0"] = str(p["B0"])
        if p.get("B0_dir"):
            env["QSMCI_B0_DIR"] = " ".join(str(x) for x in p["B0_dir"])
        if p.get("voxel_size"):
            env["QSMCI_VOXEL_SIZE"] = " ".join(str(x) for x in p["voxel_size"])
    cj = input_dir / "config.json"
    if cj.exists():
        try:
            for k, v in json.loads(cj.read_text()).items():
                env[f"QSMCI_SET_{str(k).upper()}"] = str(v)
        except Exception:  # noqa: BLE001
            pass
    return env


def _kill_named_container(runner: str, name: str, log) -> None:
    """Kill an OCI container by name. `subprocess.run(timeout=)` only kills the CLIENT process — the
    container keeps running (and holding the box's memory), since `--rm` cleans up after exit, not
    on client death. This is the same asymmetry the orphan reaper deals with after a cancelled job.
    """
    try:
        subprocess.run([runner, "kill", name], capture_output=True, timeout=_KILL_GRACE_S)
    except Exception as exc:  # noqa: BLE001 — nothing better to do than say so
        log(f"  ! could not kill container {name}: {exc}")


def _kill_process_tree(proc: "subprocess.Popen", log) -> None:
    """Kill a whole process group (apptainer/local runs are plain process trees, not daemon-owned).

    The children are what actually burn the CPU, and killing only the leader would orphan them.
    Started with start_new_session=True so the group id is the leader's pid.
    """
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(os.getpgid(proc.pid), sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            proc.wait(timeout=10)
            return
        except subprocess.TimeoutExpired:
            continue
    log(f"  ! process group {proc.pid} survived SIGKILL")


def _run_container(algo, input_dir, output_dir, runner, log, timeout: "float | None" = None) -> float:
    """Run a submission's run.sh and return its wall-clock seconds.

    `timeout` (seconds, None = uncapped) bounds the run: on expiry the container/process tree is
    killed and RunTimeout is raised, so the caller records a DNF for THIS run and carries on with
    the rest of the shard.
    """
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    penv = _param_env(input_dir)  # Layer B: acquisition params + overrides as QSMCI_* env vars
    t0 = time.time()
    if runner in _OCI_ENGINES:
        image = _build_oci(algo, runner, log)
        log(f"⚙ running container ({runner}: {image})")
        id_args = _user_args(runner)
        e_args = [a for k, v in penv.items() for a in ("-e", f"{k}={v}")]
        # Name the container so a background sampler can poll `<engine> stats <name>` for a
        # memory-over-time / CPU-over-time trace (opt-in via $QSMCI_RESOURCES_OUT).
        name = f"qsm-ci-{uuid4().hex[:12]}"
        # Label the container with the owning GitHub Actions run (when there is one) so a reaper on
        # a persistent self-hosted box can identify and kill orphans. Cancelling an Actions job kills
        # this docker CLIENT process but NOT the container (`--rm` only cleans up after exit), so
        # cancelled runs used to leave MATLAB/DL containers silently consuming the shared runner's
        # memory for hours — the workflows' "Reap orphaned containers" step keys off this label.
        label_args = ["--label", "qsmci=1"]
        if os.environ.get("GITHUB_RUN_ID"):
            label_args += ["--label", f"qsmci.run={os.environ['GITHUB_RUN_ID']}"]
        # Per-JOB tag (workflows set QSMCI_JOB_TAG = <run id>-<matrix id>): the run-level label alone
        # can't tell a failed job's leftovers from a live sibling job's containers while the run is
        # still going — observed 2026-08-27: 12-18 h of same-run orphans cascading OOM through every
        # later self-hosted job of one long full rescore. The job tag lets the post-job kill step and
        # the pre-job reaper be precise about it.
        if os.environ.get("QSMCI_JOB_TAG"):
            label_args += ["--label", f"qsmci.job={os.environ['QSMCI_JOB_TAG']}"]
        res_out = os.environ.get("QSMCI_RESOURCES_OUT")
        sampler = None
        if res_out:
            sampler = _ResourceSampler(name, runner, Path(res_out), interval=1.0)
            sampler.start()
        try:
            subprocess.run([
                runner, "run", "--rm", "--network", "none", "--name", name, *label_args,
                *_gpu_flags(runner), *id_args, *e_args,
                "-v", f"{algo['dir']}:/algo:ro",
                "-v", f"{input_dir}:/input:ro", "-v", f"{output_dir}:/output",
                image, "bash", "/algo/run.sh",
            ], check=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_named_container(runner, name, log)
            raise RunTimeout(_timeout_msg(timeout)) from None
        finally:
            if sampler is not None:
                sampler.stop()
                sampler.join(timeout=6)
                sampler.write()
    elif runner == "apptainer":
        image = _apptainer_image(algo)
        log(f"⚙ running container (apptainer: {image})")
        log("  note: apptainer runs without enforced network isolation here; CI uses --network none.")
        e_args = [a for k, v in penv.items() for a in ("--env", f"{k}={v}")]
        cmd = [
            "apptainer", "exec", "--no-home", "--cleanenv", *_gpu_flags("apptainer"), *e_args,
            "-B", f"{algo['dir']}:/algo:ro",
            "-B", f"{input_dir}:/input:ro", "-B", f"{output_dir}:/output",
            image, "bash", "/algo/run.sh",
        ]
        # apptainer has no `stats`, so sample the process TREE via /proc for the memory/CPU trace
        # (opt-in via $QSMCI_RESOURCES_OUT) — Popen to get the pid, then wait as `run(check=True)` would.
        res_out = os.environ.get("QSMCI_RESOURCES_OUT")
        proc = subprocess.Popen(cmd, start_new_session=True)   # own process group, so it can be killed whole
        sampler = _ProcResourceSampler(proc.pid, Path(res_out), interval=1.0) if res_out else None
        if sampler is not None:
            sampler.start()
        try:
            try:
                rc = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_process_tree(proc, log)
                raise RunTimeout(_timeout_msg(timeout)) from None
            if rc != 0:
                raise subprocess.CalledProcessError(rc, cmd)
        finally:
            if sampler is not None:
                sampler.stop()
                sampler.join(timeout=6)
                sampler.write()
    else:  # local
        log("⚙ running run.sh directly (--runner local)")
        cmd = ["bash", str(algo["dir"] / "run.sh"), str(input_dir), str(output_dir)]
        proc = subprocess.Popen(cmd, env={**os.environ, **penv}, start_new_session=True)
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_process_tree(proc, log)
            raise RunTimeout(_timeout_msg(timeout)) from None
        if rc != 0:
            raise subprocess.CalledProcessError(rc, cmd)
    return time.time() - t0
