"""`qsm-ci run` — run one stage on explicit input files, and score it if a truth is given.

No BIDS, no datasets, no downloads: you point at the exact NIfTIs a stage consumes. The accepted
`--<artifact>` flags are generated from the submission's stage (see stages.py), so
`qsm-ci run <slug> --help` shows precisely what that method needs. Pass `--truth` (and optionally
`--seg`) to score the output with qsm_ci.qsm_eval — the same scorer the online CI uses.
"""

from __future__ import annotations

import argparse
import difflib
import glob
import gzip
import json
import math
import os
import re
import shutil
import struct
import subprocess
import time
from pathlib import Path

from .stages import ARTIFACT_FILE, ARTIFACT_KIND, STAGES

# Consumed artifacts that aren't required to run a stage (only some methods use them, e.g. MEDI
# uses magnitude; plain TKD does not). Everything else the stage consumes is required.
OPTIONAL_ARTIFACTS = {"magnitude"}

# Multi-echo artifacts: a stage wants one 4D NIfTI (x,y,z,echo), but a caller with BIDS data has one
# 3D file per echo. These flags accept several files and we stack them into the 4D artifact.
STACKABLE_ARTIFACTS = {"phase", "magnitude"}


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


def _find_algo_dir(target: str) -> "Path | None":
    """Resolve a slug (algorithms/<slug> or ./<slug>) or a direct path; None if not found.

    $QSMCI_ALGORITHMS, if set, is searched too — so a bare slug resolves even when the cwd isn't a
    QSM-CI checkout (e.g. inside a Nextflow/CWL process that runs in its own isolated work dir)."""
    p = Path(target)
    cands = [p, Path("algorithms") / target, Path.cwd() / target]
    env = os.environ.get("QSMCI_ALGORITHMS")
    if env:
        cands.append(Path(env) / target)
    for cand in cands:
        if (cand / "algorithm.yml").exists():
            return cand.resolve()
    return None


def resolve_algo_dir(target: str) -> Path:
    """Accept a slug (algorithms/<slug> or ./<slug>) or a direct path to the folder."""
    d = _find_algo_dir(target)
    if d is None:
        raise SystemExit(f"could not find an algorithm.yml for '{target}' "
                         f"(looked at {target}, algorithms/{target})")
    return d


def _algorithms_root() -> "Path | None":
    env = os.environ.get("QSMCI_ALGORITHMS")
    cands = [Path("algorithms"), Path.cwd() / "algorithms"]
    if env:
        cands.insert(0, Path(env))
    for cand in cands:
        if cand.is_dir():
            return cand
    return None


def _registry_algorithms() -> "list[tuple[str, str, str]]":
    """(slug, stage, name) from the shipped Zenodo registry — the published methods a bare
    pip install can fetch and run, used when there's no local checkout."""
    try:
        from .registry import load_mapping
        mapping = load_mapping()
    except Exception:  # noqa: BLE001 — best-effort; an unreadable registry just yields nothing
        return []
    return [(slug, mapping[slug].get("stage") or "?", mapping[slug].get("name") or slug)
            for slug in sorted(mapping)]


def _list_algorithms() -> "list[tuple[str, str, str]]":
    """(slug, stage, name) for every runnable submission under ./algorithms (skips _internal).

    With no local checkout (a bare pip install), fall back to the shipped registry — those are
    exactly the methods `qsm-ci run <slug>` can fetch from Zenodo."""
    root = _algorithms_root()
    if root is None:
        return _registry_algorithms()
    out = []
    for d in sorted(root.iterdir()):
        if d.name.startswith("_") or not (d / "algorithm.yml").exists():
            continue
        stage = name = ""
        for line in (d / "algorithm.yml").read_text().splitlines():
            s = line.strip()
            if s.startswith("stage:") and not stage:
                stage = s.split(":", 1)[1].strip()
            elif s.startswith("name:") and not name:
                name = s.split(":", 1)[1].strip().strip('"\'')
        out.append((d.name, stage or "?", name or d.name))
    return out


def _algorithms_help() -> str:
    """A grouped listing of runnable slugs, or guidance if there's no algorithms/ here."""
    algos = _list_algorithms()
    if not algos:
        return ("No algorithms found. Run qsm-ci from a QSM-CI checkout\n"
                "(git clone https://github.com/QSMxT/QSM-CI), or pass a path to a submission folder.")
    width = max(len(slug) for slug, _, _ in algos)
    by_stage: dict[str, list[tuple[str, str]]] = {}
    for slug, stage, name in algos:
        by_stage.setdefault(stage, []).append((slug, name))
    header = ("Published methods (fetched from Zenodo on first run) — run  qsm-ci run <slug>  to see the inputs each needs:"
              if _algorithms_root() is None else
              "Available algorithms — run  qsm-ci run <slug>  to see the inputs each needs:")
    lines = [header, ""]
    for stage in sorted(by_stage):
        lines.append(f"  {stage}:")
        for slug, name in by_stage[stage]:
            lines.append(f"    {slug.ljust(width)}   {name}")
    return "\n".join(lines)


def _closest_slugs(target: str) -> "list[str]":
    names = [slug for slug, _, _ in _list_algorithms()]
    return difflib.get_close_matches(target, names, n=3, cutoff=0.4)


def _nifti_voxel_size(path) -> "list[float] | None":
    """Read pixdim[1:4] (mm) straight from a NIfTI-1 header — no nibabel dependency."""
    if not path or not Path(path).exists():
        return None
    opener = gzip.open if str(path).endswith(".gz") else open
    try:
        with opener(path, "rb") as f:
            hdr = f.read(352)
        if len(hdr) < 352:
            return None
        for endian in ("<", ">"):  # header endianness is whichever makes sizeof_hdr == 348
            if struct.unpack(endian + "i", hdr[0:4])[0] == 348:
                pixdim = struct.unpack(endian + "8f", hdr[76:108])
                vs = [abs(pixdim[1]), abs(pixdim[2]), abs(pixdim[3])]
                return vs if all(v > 0 for v in vs) else None
    except Exception:  # noqa: BLE001 — best-effort; caller falls back to a default
        return None
    return None


def _place_input(src, dest: Path) -> None:
    """Put a consumed NIfTI at <name>.nii.gz, gzip-compressing a plain .nii on the way in."""
    src = str(src)
    if src.endswith(".nii") and str(dest).endswith(".nii.gz"):
        with open(src, "rb") as fi, gzip.open(dest, "wb") as fo:
            shutil.copyfileobj(fi, fo)
    else:
        shutil.copy(src, dest)


def _echo_key(path) -> int:
    m = re.search(r"echo-?(\d+)", str(path))
    return int(m.group(1)) if m else 0


def _place_echoes(paths: list, dest: Path, log) -> None:
    """Place a multi-echo artifact: one file goes in as-is; several 3D echoes are stacked into 4D.

    When every filename carries a BIDS `echo-<n>`, echoes are ordered by that number (so echo-10
    sorts after echo-2); otherwise the given order is kept. The stacked file must line up with the
    `TE` list in params.json."""
    if len(paths) == 1:
        _place_input(paths[0], dest)
        return
    import nibabel as nib
    import numpy as np
    ordered = sorted(paths, key=_echo_key) if all(re.search(r"echo-?\d+", str(p)) for p in paths) else list(paths)
    imgs = [nib.load(str(p)) for p in ordered]
    data = np.stack([im.get_fdata(dtype=np.float64) for im in imgs], axis=-1)
    dest.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(data.astype(np.float32), imgs[0].affine), str(dest))
    log(f"  stacked {len(ordered)} echoes → {dest.name}")


def _params_dict(args, stage: str) -> dict:
    """Assemble a params.json dict from --te/--field-strength/--b0-dir/--voxel-size (+ defaults).

    B0_dir defaults to +z; voxel size is read from the primary input's NIfTI header when not given.
    Echo times and field strength are only required for stages that consume phase (field-mapping);
    BFR/dipole work in ppm and don't use them, so they get harmless placeholders.
    """
    consumes = STAGES[stage]["consumes"]
    needs_echo = "phase" in consumes
    te = list(args.te) if args.te else []
    b0 = args.field_strength
    if needs_echo and (not te or b0 is None):
        raise SystemExit(
            f"the {stage} stage needs echo times and field strength — pass "
            "--te SEC [SEC ...] and --field-strength TESLA, or give a --params file.")
    if b0 is None:
        b0 = 3.0  # unused by BFR/dipole; a contract placeholder
    b0_dir = list(args.b0_dir) if args.b0_dir is not None else [0.0, 0.0, 1.0]
    if args.voxel_size is not None:
        voxel = list(args.voxel_size)
    else:
        primary = getattr(args, consumes[0], None)
        voxel = _nifti_voxel_size(primary) or [1.0, 1.0, 1.0]
    return {"TE": [float(t) for t in te], "B0": float(b0),
            "B0_dir": [float(x) for x in b0_dir], "voxel_size": [float(v) for v in voxel]}


def _looks_like_sidecar(obj: dict) -> bool:
    """A BIDS MEGRE sidecar carries these keys; a QSM-CI params.json does not."""
    return isinstance(obj, dict) and ("EchoTime" in obj or "MagneticFieldStrength" in obj)


def _sidecar_te(sidecar_path: Path) -> "list[float]":
    """Echo times (s) for the whole acquisition: all `*part-phase*MEGRE.json` in the sidecar's
    directory, in echo order. Falls back to just this file's EchoTime."""
    def echo_no(f: str) -> int:
        m = re.search(r"echo-(\d+)", f)
        return int(m.group(1)) if m else 0
    tes = []
    for f in sorted(glob.glob(str(sidecar_path.parent / "*part-phase*MEGRE.json")), key=echo_no):
        try:
            v = json.load(open(f)).get("EchoTime")
        except Exception:  # noqa: BLE001
            v = None
        if v is not None:
            tes.append(float(v))
    if not tes:
        v = json.load(open(sidecar_path)).get("EchoTime")
        tes = [float(v)] if v is not None else []
    return tes


def _sidecar_to_params(path: Path, obj: dict, args, stage: str) -> dict:
    """Map a BIDS MEGRE phase sidecar onto the QSM-CI params.json schema.

    Voxel size is read from the input NIfTI header (the authoritative grid); the sidecar's
    `VoxelSize` is only a fallback. Any explicit acquisition flag the user passed wins.
    """
    consumes = STAGES[stage]["consumes"]
    primary = getattr(args, consumes[0], None)
    te = _sidecar_te(path)
    b0 = obj.get("MagneticFieldStrength", 3.0)
    b0_dir = obj.get("B0_dir") or [0.0, 0.0, 1.0]
    voxel = _nifti_voxel_size(primary) or obj.get("VoxelSize") or [1.0, 1.0, 1.0]
    if args.te:
        te = args.te
    if args.field_strength is not None:
        b0 = args.field_strength
    if args.b0_dir is not None:
        b0_dir = args.b0_dir
    if args.voxel_size is not None:
        voxel = args.voxel_size
    return {"TE": [float(t) for t in te], "B0": float(b0),
            "B0_dir": [float(x) for x in b0_dir], "voxel_size": [float(v) for v in voxel]}


def _inputs_summary(slug: str, algo: dict) -> str:
    """Tell the user exactly which inputs a valid slug's stage needs, with an example."""
    stage = algo["stage"]
    consumes = STAGES[stage]["consumes"]
    produced = STAGES[stage]["produces"][0]
    needs_echo = "phase" in consumes
    lines = [f"{algo['name']}  —  {stage} stage   ({', '.join(consumes)} → {produced})", "",
             "Image inputs (provide each as a file):"]
    for art in consumes:
        if art == "params":
            continue
        opt = "  [optional]" if art in OPTIONAL_ARTIFACTS else ""
        lines.append(f"  --{art} PATH".ljust(22) + f"{ARTIFACT_FILE[art]} (NIfTI){opt}")
    lines += ["", "Acquisition parameters — give a params.json OR the flags (either works):",
              "  --params PATH".ljust(22) + "params.json"]
    tag = "   [required here]"
    lines.append("  --te SEC [SEC ...]".ljust(22) + "echo times, seconds" + (tag if needs_echo else ""))
    lines.append("  --field-strength T".ljust(22) + "B0 in tesla" + (tag if needs_echo else ""))
    lines.append("  --b0-dir X Y Z".ljust(22) + "unit B0 direction (default: 0 0 1)")
    lines.append("  --voxel-size X Y Z".ljust(22) + "mm (default: from the input header)")
    req_imgs = [a for a in consumes if a not in OPTIONAL_ARTIFACTS and a != "params"]
    example = " ".join(f"--{a} {a}.nii.gz" for a in req_imgs)
    if needs_echo:
        example += " --te 0.004 0.012 0.02 0.028 --field-strength 7"
    lines += ["",
              f"Example:  qsm-ci run {slug} {example}",
              f"Add  --truth {produced}.nii.gz  [--seg dseg.nii.gz]  to score the output.",
              f"See   qsm-ci run {slug} --help  for runner/scoring options and method parameters."]
    return "\n".join(lines)


def list_command(argv=None, log=print) -> int:
    """`qsm-ci list` — show the reference algorithms available to run."""
    log(_algorithms_help())
    return 0


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
        subprocess.run([
            runner, "run", "--rm", "--network", "none", *id_args, *e_args,
            "-v", f"{algo['dir']}:/algo:ro",
            "-v", f"{input_dir}:/input:ro", "-v", f"{output_dir}:/output",
            image, "bash", "/algo/run.sh",
        ], check=True)
    elif runner == "apptainer":
        image = _apptainer_image(algo)
        log(f"⚙ running container (apptainer: {image})")
        log("  note: apptainer runs without enforced network isolation here; CI uses --network none.")
        e_args = [a for k, v in penv.items() for a in ("--env", f"{k}={v}")]
        subprocess.run([
            "apptainer", "exec", "--no-home", "--cleanenv", *e_args,
            "-B", f"{algo['dir']}:/algo:ro",
            "-B", f"{input_dir}:/input:ro", "-B", f"{output_dir}:/output",
            image, "bash", "/algo/run.sh",
        ], check=True)
    else:  # local
        log("⚙ running run.sh directly (--runner local)")
        subprocess.run(["bash", str(algo["dir"] / "run.sh"), str(input_dir), str(output_dir)],
                       check=True, env={**os.environ, **penv})
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
        if art == "params":
            p.add_argument("--params", metavar="PATH", required=False,
                           help="params.json or a BIDS MEGRE sidecar — or use the acquisition flags below")
            continue
        req = art not in OPTIONAL_ARTIFACTS
        if art in STACKABLE_ARTIFACTS:
            # multi-echo: accept one 4D file OR several per-echo 3D files (BIDS-style), stacked to 4D.
            p.add_argument(f"--{art}", metavar="PATH", nargs="+", required=req,
                           help=f"{ARTIFACT_FILE[art]} — one 4D file, or per-echo 3D files to stack"
                                + ("" if req else "  [optional]"))
        else:
            p.add_argument(f"--{art}", metavar="PATH", required=req,
                           help=f"{ARTIFACT_FILE[art]} (NIfTI)" + ("" if req else "  [optional]"))
    acq = p.add_argument_group("acquisition parameters (build params.json when --params is omitted)")
    acq.add_argument("--te", nargs="+", type=float, metavar="SEC",
                     help="echo times in seconds (required for field-mapping stages)")
    acq.add_argument("--field-strength", "--b0", dest="field_strength", type=float, metavar="TESLA",
                     help="B0 field strength (required for field-mapping stages)")
    acq.add_argument("--b0-dir", nargs=3, type=float, metavar=("X", "Y", "Z"),
                     help="unit B0 direction (default: 0 0 1)")
    acq.add_argument("--voxel-size", nargs=3, type=float, metavar=("X", "Y", "Z"),
                     help="voxel size in mm (default: read from the input NIfTI header)")
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
    has_help = any(a in ("-h", "--help") for a in argv)
    slug = next((a for a in argv if not a.startswith("-")), None)

    # No slug (incl. bare `--help`): show what you can run instead of a dead-end usage line.
    if not slug:
        log("usage: qsm-ci run <slug> [--<artifact> PATH ...] [--truth PATH] [-o OUT]")
        log("")
        log(_algorithms_help())
        return 0 if has_help else 2

    # Resolve locally first (a checkout / $QSMCI_ALGORITHMS), else fetch it from the Zenodo
    # registry (a bare slug, a pinned `slug@version`, or a `doi:` reference).
    algo_dir = _find_algo_dir(slug)
    if algo_dir is None:
        try:
            from .registry import resolve as _registry_resolve
            algo_dir = _registry_resolve(slug, log)
        except Exception as e:  # noqa: BLE001 — network/registry issues shouldn't crash; fall through to guidance
            log(f"  (registry lookup failed: {e})")
    if algo_dir is None:
        log(f"✗ no submission '{slug}' (looked at {slug}, algorithms/{slug}, and the Zenodo registry).")
        hint = _closest_slugs(slug)
        if hint:
            log(f"  did you mean:  {', '.join(hint)}")
        log("")
        log(_algorithms_help())
        return 2

    algo = _parse_manifest(algo_dir)

    # `qsm-ci run <slug>` with no input files (and not --help): tell them what to provide.
    artifact_flags = {f"--{art}" for art in STAGES[algo["stage"]]["consumes"]}
    gave_input = any(a.split("=", 1)[0] in artifact_flags for a in argv)
    if not has_help and not gave_input:
        log(_inputs_summary(slug, algo))
        return 0

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
            if art == "params":
                dest = idir / ARTIFACT_FILE["params"]
                if args.params:
                    src = Path(args.params)
                    if not src.exists():
                        raise SystemExit(f"--params file not found: {src}")
                    try:
                        obj = json.loads(src.read_text())
                    except Exception as e:  # noqa: BLE001
                        raise SystemExit(f"--params is not valid JSON: {e}")
                    if _looks_like_sidecar(obj):
                        params = _sidecar_to_params(src, obj, args, stage)
                        dest.write_text(json.dumps(params, indent=2) + "\n")
                        log(f"  params (from BIDS sidecar): TE={params['TE']} B0={params['B0']} "
                            f"B0_dir={params['B0_dir']} voxel_size={params['voxel_size']}")
                    else:
                        shutil.copy(src, dest)  # already a params.json — use verbatim
                else:
                    params = _params_dict(args, stage)
                    dest.write_text(json.dumps(params, indent=2) + "\n")
                    log(f"  params: TE={params['TE']} B0={params['B0']} "
                        f"B0_dir={params['B0_dir']} voxel_size={params['voxel_size']}")
                continue
            value = getattr(args, art, None)
            if not value:
                continue  # optional and not supplied
            paths = value if isinstance(value, list) else [value]
            for pth in paths:
                if not Path(pth).exists():
                    raise SystemExit(f"--{art} file not found: {pth}")
            if art in STACKABLE_ARTIFACTS:
                _place_echoes(paths, idir / ARTIFACT_FILE[art], log)
            else:
                _place_input(paths[0], idir / ARTIFACT_FILE[art])

        if cfg:
            (idir / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")

        runtime = _run_container(algo, idir, odir, args.runner, log)

        produced_tmp = odir / ARTIFACT_FILE[produced]
        if not produced_tmp.exists():
            raise SystemExit(f"submission did not write {ARTIFACT_FILE[produced]} to /output")
        out_path = Path(args.out)
        if out_path.is_dir():
            out_path = out_path / ARTIFACT_FILE[produced]  # -o <dir> → write <dir>/<artifact>
        if str(out_path.parent):
            out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(produced_tmp, out_path)
        log(f"✓ wrote {out_path}  ({runtime:.1f}s)")

        if args.truth:
            metrics = _score(out_path, produced, Path(args.truth), Path(args.mask), args.seg)
            _print_metrics(algo["name"], stage, produced, runtime, metrics, log)
        else:
            log("  (no --truth given → not scored)")
    return 0
