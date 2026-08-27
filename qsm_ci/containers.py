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
import subprocess
import time
from pathlib import Path
from uuid import uuid4

from .resources import _ResourceSampler, _ProcResourceSampler
from .stages import ARTIFACT_FILE

RUNNERS = ("docker", "podman", "apptainer", "local")
_OCI_ENGINES = ("docker", "podman")  # daemonless podman is CLI-compatible with docker


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


def check_runner(runner: str) -> bool:
    """Is the tooling for this runner available?"""
    if runner == "local":
        return True
    if runner == "docker":  # also confirm the daemon answers
        try:
            return subprocess.run(["docker", "version"], capture_output=True).returncode == 0
        except FileNotFoundError:
            return False
    return _have(runner)


def check_docker() -> bool:  # kept for back-compat
    return check_runner("docker")


def _build_oci(algo: dict, engine: str, log) -> str:
    """docker/podman: PULL the submission's prebuilt image: and return its ref — never build.

    CI must not build containers. Every submission publishes a prebuilt ``image:``; a folder
    Dockerfile is only the build recipe (used out-of-band to produce that image), never built here.
    Pull the tag; if the pull fails (offline / registry hiccup) fall back to a locally cached copy;
    if neither is available, stop with a clear message telling the author to build and push first."""
    tag = algo.get("image")
    if not tag:
        raise SystemExit(
            "algorithm.yml has no image:. Publish a prebuilt image (build and push it first) and set "
            "image: to its reference — the runner pulls images, it does not build containers.")
    log(f"↓ pulling {tag}")
    if subprocess.run([engine, "pull", tag], capture_output=True).returncode != 0:
        # Offline / registry hiccup — fall back to a locally cached copy if one exists.
        if subprocess.run([engine, "image", "inspect", tag], capture_output=True).returncode != 0:
            raise SystemExit(
                f"could not pull {tag} and no local copy is cached. Build and push the image first; "
                "the runner does not build containers (a folder Dockerfile is only the build recipe).")
        log(f"  (pull failed — using locally cached {tag})")
    return tag


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
    if (algo["dir"] / "Dockerfile").exists():
        raise SystemExit(
            "apptainer can't build a Dockerfile. Build it first with --runner docker/podman, "
            "or set image: to a prebuilt reference (docker://…, a registry ref, or a .sif).")
    raise SystemExit("algorithm.yml has no image: for apptainer to run")


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


def _run_container(algo, input_dir, output_dir, runner, log) -> float:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    penv = _param_env(input_dir)  # Layer B: acquisition params + overrides as QSMCI_* env vars
    t0 = time.time()
    if runner in _OCI_ENGINES:
        image = _build_oci(algo, runner, log)
        log(f"⚙ running container ({runner}: {image})")
        # rootless podman: keep-id maps your host uid inside, so files written to the /output
        # bind mount come back owned by you. docker (root daemon): run as your uid directly.
        id_args = (["--userns=keep-id"] if runner == "podman"
                   else ["--user", f"{os.getuid()}:{os.getgid()}"])
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
            ], check=True)
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
        proc = subprocess.Popen(cmd)
        sampler = _ProcResourceSampler(proc.pid, Path(res_out), interval=1.0) if res_out else None
        if sampler is not None:
            sampler.start()
        try:
            rc = proc.wait()
            if rc != 0:
                raise subprocess.CalledProcessError(rc, cmd)
        finally:
            if sampler is not None:
                sampler.stop()
                sampler.join(timeout=6)
                sampler.write()
    else:  # local
        log("⚙ running run.sh directly (--runner local)")
        subprocess.run(["bash", str(algo["dir"] / "run.sh"), str(input_dir), str(output_dir)],
                       check=True, env={**os.environ, **penv})
    return time.time() - t0
