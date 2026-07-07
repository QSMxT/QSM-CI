"""`qsm-ci run` — run one stage on explicit input files, and score it if a truth is given.

No BIDS, no datasets, no downloads: you point at the exact NIfTIs a stage consumes. The accepted
`--<artifact>` flags are generated from the submission's stage (see stages.py), so
`qsm-ci run <slug> --help` shows precisely what that method needs. Pass `--truth` (and optionally
`--seg`) to score the output with qsm_ci.qsm_eval — the same scorer the online CI uses.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path

from .stages import ARTIFACT_FILE, ARTIFACT_KIND, STAGES

# Consumed artifacts that aren't required to run a stage (only some methods use them, e.g. MEDI
# uses magnitude; plain TKD does not). Everything else the stage consumes is required.
OPTIONAL_ARTIFACTS = {"magnitude"}


def _parse_manifest(algo_dir: Path) -> dict:
    spec = algo_dir / "algorithm.yml"
    if not spec.exists():
        raise SystemExit(f"no algorithm.yml in {algo_dir}")
    try:
        import yaml
    except ImportError:
        raise SystemExit("PyYAML is required to read algorithm.yml — pip install pyyaml")
    meta = yaml.safe_load(spec.read_text()) or {}
    stage = meta.get("stage")
    if stage not in STAGES:
        raise SystemExit(f"algorithm.yml stage '{stage}' is not a known stage/span")
    meta["dir"] = algo_dir
    meta.setdefault("name", algo_dir.name)
    meta.setdefault("slug", algo_dir.name)
    return meta


def resolve_algo_dir(target: str) -> Path:
    """Accept a slug (algorithms/<slug> or ./<slug>) or a direct path to the folder."""
    p = Path(target)
    for cand in (p, Path("algorithms") / target, Path.cwd() / target):
        if (cand / "algorithm.yml").exists():
            return cand.resolve()
    raise SystemExit(f"could not find an algorithm.yml for '{target}' "
                     f"(looked at {p}, algorithms/{target})")


RUNNERS = ("docker", "podman", "apptainer", "local")
_OCI_ENGINES = ("docker", "podman")  # daemonless podman is CLI-compatible with docker


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
    """docker/podman: build a Dockerfile if present, else pull image:. Returns the image ref."""
    if (algo["dir"] / "Dockerfile").exists():
        tag = f"qsm-ci-local/{algo['slug']}:latest"
        log(f"⚙ building image from Dockerfile → {tag}")
        subprocess.run([engine, "build", "-q", "-t", tag, str(algo["dir"])], check=True)
        return tag
    tag = algo["image"]
    if not tag:
        raise SystemExit("algorithm.yml has no image: and no Dockerfile to build")
    if subprocess.run([engine, "image", "inspect", tag], capture_output=True).returncode != 0:
        log(f"↓ pulling {tag}")
        subprocess.run([engine, "pull", tag], check=True)
    return tag


def _apptainer_image(algo: dict) -> str:
    """apptainer runs from a docker:// ref or a .sif — it can't build a Dockerfile itself."""
    if (algo["dir"] / "Dockerfile").exists():
        raise SystemExit(
            "apptainer can't build a Dockerfile. Build it first with --runner docker/podman, "
            "or set image: to a prebuilt reference (docker://…, a registry ref, or a .sif).")
    img = algo["image"]
    if not img:
        raise SystemExit("algorithm.yml has no image: for apptainer to run")
    if "://" in img or img.endswith(".sif") or os.path.exists(img):
        return img
    return f"docker://{img}"  # plain registry ref -> pull & convert on the fly


def _run_container(algo, input_dir, output_dir, runner, log) -> float:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    t0 = time.time()
    if runner in _OCI_ENGINES:
        image = _build_oci(algo, runner, log)
        log(f"⚙ running container ({runner}: {image})")
        subprocess.run([
            runner, "run", "--rm", "--network", "none",
            "--user", f"{os.getuid()}:{os.getgid()}",
            "-v", f"{algo['dir']}:/algo:ro",
            "-v", f"{input_dir}:/input:ro", "-v", f"{output_dir}:/output",
            image, "bash", "/algo/run.sh",
        ], check=True)
    elif runner == "apptainer":
        image = _apptainer_image(algo)
        log(f"⚙ running container (apptainer: {image})")
        log("  note: apptainer runs without enforced network isolation here; CI uses --network none.")
        subprocess.run([
            "apptainer", "exec", "--no-home", "--cleanenv",
            "-B", f"{algo['dir']}:/algo:ro",
            "-B", f"{input_dir}:/input:ro", "-B", f"{output_dir}:/output",
            image, "bash", "/algo/run.sh",
        ], check=True)
    else:  # local
        log("⚙ running run.sh directly (--runner local)")
        subprocess.run(["bash", str(algo["dir"] / "run.sh"), str(input_dir), str(output_dir)],
                       check=True)
    return time.time() - t0


def _score(recon: Path, artifact: str, truth: Path, mask: Path, seg: "Path | None") -> dict:
    from . import qsm_eval
    kind = ARTIFACT_KIND[artifact]
    r, t, m = qsm_eval.load(recon), qsm_eval.load(truth), qsm_eval.load(mask)
    if r.shape != t.shape or r.shape != m.shape:
        raise SystemExit(f"shape mismatch: recon {r.shape}, truth {t.shape}, mask {m.shape}")
    if kind == "field":
        return qsm_eval.field_metrics(r, t, m)
    if seg and Path(seg).exists():
        import numpy as np
        return qsm_eval.challenge_metrics(r, t, m, np.rint(qsm_eval.load(seg)).astype("int32"))
    return {"correlation": qsm_eval.correlation(r, t, m), "xsim": qsm_eval.xsim(r, t, m)}


def _print_metrics(name, stage, artifact, runtime, metrics, log):
    log("")
    log(f"  {name}  ·  {stage} → {artifact}  ·  {runtime:.1f}s")
    log("  " + "─" * 34)
    for key, val in metrics.items():
        if isinstance(val, float) and math.isnan(val):
            shown = "—"
        elif isinstance(val, float):
            shown = f"{val:.4f}"
        else:
            shown = str(val)
        log(f"  {key:<20} {shown:>12}")
    log("")


class _HelpFmt(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    """Show argument defaults AND keep newlines in the description/epilog."""


def _manifest_epilog(algo: dict) -> "str | None":
    lines = []
    params = algo.get("parameters") or []
    if params:
        lines.append("method parameters — override with --set NAME=VALUE (else the method's default):")
        width = max((len(str(p.get("name", ""))) for p in params), default=0)
        for p in params:
            name = str(p.get("name", "")).ljust(width)
            default = p.get("default")
            desc = p.get("description", "")
            lines.append(f"  {name}  = {default!s:<8} {desc}")
    cite, doi = algo.get("citation"), algo.get("doi")
    if cite and cite != "null":
        ref = f"reference: {cite}"
        if doi and doi != "null":
            ref += f"   doi:{doi}"
        lines.append("")
        lines.append(ref)
    return "\n".join(lines) if lines else None


def _build_run_parser(slug: str, algo: dict) -> argparse.ArgumentParser:
    stage = algo["stage"]
    consumes = STAGES[stage]["consumes"]
    produced = STAGES[stage]["produces"][0]
    desc = f"{algo['name']} — {stage} stage  ({', '.join(consumes)} → {produced})"
    if algo.get("description"):
        desc += "\n\n" + " ".join(str(algo["description"]).split())
    p = argparse.ArgumentParser(
        prog=f"qsm-ci run {slug}", description=desc,
        epilog=_manifest_epilog(algo), formatter_class=_HelpFmt)
    p.add_argument("slug", help=argparse.SUPPRESS)  # already known; keep argparse happy
    for art in consumes:
        req = art not in OPTIONAL_ARTIFACTS
        ftype = "JSON" if art == "params" else "NIfTI"
        p.add_argument(f"--{art}", metavar="PATH", required=req,
                       help=f"{ARTIFACT_FILE[art]} ({ftype})" + ("" if req else "  [optional]"))
    p.add_argument("-o", "--out", metavar="PATH", default=f"{produced}.nii.gz",
                   help="where to write the produced artifact")
    p.add_argument("--truth", metavar="PATH", help=f"ground-truth {produced} to score against")
    p.add_argument("--seg", metavar="PATH", help="segmentation (enables full χ region metrics)")
    p.add_argument("--runner", choices=list(RUNNERS), default="docker",
                   help="docker/podman/apptainer run the image; local runs run.sh on the host")
    p.add_argument("--set", action="append", default=[], dest="overrides", metavar="NAME=VALUE",
                   help="override a method parameter (repeatable); valid names listed below")
    return p


def _coerce(v: str):
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    return v


def _overrides(algo: dict, items: list) -> dict:
    declared = {str(p.get("name")): p for p in (algo.get("parameters") or [])}
    cfg = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"--set expects NAME=VALUE, got '{item}'")
        k, v = item.split("=", 1)
        if k not in declared:
            valid = ", ".join(declared) or "(this method declares no parameters)"
            raise SystemExit(f"unknown parameter '{k}'. valid: {valid}")
        cfg[k] = _coerce(v)
    return cfg


def run_command(argv, log=print) -> int:
    """Dispatch `qsm-ci run ...` with flags derived from the submission's stage."""
    slug = next((a for a in argv if not a.startswith("-")), None)
    if not slug:
        log("usage: qsm-ci run <slug> [--<artifact> PATH ...] [--truth PATH] [-o OUT]")
        log("The accepted --<artifact> flags depend on the submission's stage.")
        log("Run  qsm-ci run <slug> --help  to see them.")
        return 2

    algo = _parse_manifest(resolve_algo_dir(slug))
    parser = _build_run_parser(slug, algo)
    args = parser.parse_args(argv)

    cfg = _overrides(algo, args.overrides)  # validate --set up front, before any work

    if not check_runner(args.runner):
        hint = ("Install/start Docker" if args.runner == "docker" else f"'{args.runner}' not found")
        log(f"! {args.runner} runner unavailable — {hint}. "
            f"Try another --runner ({', '.join(RUNNERS)}); 'local' runs run.sh on the host.")
        return 1

    stage = algo["stage"]
    consumes = STAGES[stage]["consumes"]
    produced = STAGES[stage]["produces"][0]

    import tempfile
    log(f"▸ {algo['name']}  [{stage}]  runner={args.runner}")
    if cfg:
        log(f"  overrides: {cfg}")
    with tempfile.TemporaryDirectory(prefix="qsm-ci-") as td:
        idir, odir = Path(td) / "input", Path(td) / "output"
        idir.mkdir(parents=True)
        for art in consumes:
            path = getattr(args, art, None)
            if not path:
                continue  # optional and not supplied
            if not Path(path).exists():
                raise SystemExit(f"--{art} file not found: {path}")
            shutil.copy(path, idir / ARTIFACT_FILE[art])

        if cfg:
            (idir / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")

        runtime = _run_container(algo, idir, odir, args.runner, log)

        produced_tmp = odir / ARTIFACT_FILE[produced]
        if not produced_tmp.exists():
            raise SystemExit(f"submission did not write {ARTIFACT_FILE[produced]} to /output")
        out_path = Path(args.out)
        if out_path.parent != Path(""):
            out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(produced_tmp, out_path)
        log(f"✓ wrote {out_path}  ({runtime:.1f}s)")

        if args.truth:
            metrics = _score(out_path, produced, Path(args.truth), Path(args.mask), args.seg)
            _print_metrics(algo["name"], stage, produced, runtime, metrics, log)
        else:
            log("  (no --truth given → not scored)")
    return 0
