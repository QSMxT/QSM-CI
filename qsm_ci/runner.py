"""`qsm-ci run` — run one stage on explicit input files, and score it if a truth is given.

No BIDS, no datasets, no downloads: you point at the exact NIfTIs a stage consumes. The accepted
`--<artifact>` flags are generated from the submission's stage (see stages.py), so
`qsm-ci run <slug> --help` shows precisely what that method needs. Pass `--truth` (and optionally
`--seg`) to score the output with qsm_ci.qsm_eval — the same scorer the online CI uses.
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import os
import shutil
from pathlib import Path

from .containers import (RUNNERS, _run_container, check_docker,  # noqa: F401 — check_docker re-exported for back-compat
                         check_runner)
from .resources import _ResourceSampler  # noqa: F401 — re-exported for the sampler regression test
from .params import (OPTIONAL_ARTIFACTS, STACKABLE_ARTIFACTS, _looks_like_sidecar,
                     _params_dict, _params_summary, _place_echoes,
                     _place_input, _sidecar_to_params)
from .stages import ARTIFACT_FILE, ARTIFACT_KIND, STAGES


def _consumes(algo: dict) -> list:
    """Artifacts a method actually takes as input — so the CLI only suggests flags the method uses.

    A method may declare an explicit `inputs:` list in algorithm.yml (the exact artifacts its code
    reads); when present we return that, intersected with the stage contract and kept in stage order,
    so a chi-separation net that ignores `magnitude` doesn't advertise `--magnitude`. Without it we
    fall back to the stage's full `consumes` plus any `optional_inputs:` the method opts into — the
    additive default (the plain `dipole` stage takes only the local field; MEDI opts into magnitude
    for data-consistency weighting so only *its* help lists --magnitude)."""
    base = STAGES[algo["stage"]]["consumes"]
    explicit = algo.get("inputs")
    if explicit:
        want = set(explicit)
        return [a for a in base if a in want]  # stage order; only what the method declares it reads
    extra = [a for a in (algo.get("optional_inputs") or [])
             if a in OPTIONAL_ARTIFACTS and a not in base]
    return base + extra


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



def _inputs_summary(slug: str, algo: dict) -> str:
    """Tell the user exactly which inputs a valid slug's stage needs, with an example."""
    stage = algo["stage"]
    consumes = _consumes(algo)
    prods = STAGES[stage]["produces"]
    produced = prods[0]
    needs_echo = "phase" in consumes
    img_inputs = [a for a in consumes if a != "params"]
    lines = [f"{algo['name']}  —  {stage} stage   ({', '.join(consumes)} → {', '.join(prods)})", "",
             "Image inputs (provide each as a file):"]
    for art in consumes:
        if art == "params":
            continue
        # a normally-optional artifact is required when it's the stage's sole image input (see parser).
        opt = "  [optional]" if (art in OPTIONAL_ARTIFACTS and img_inputs != [art]) else ""
        lines.append(f"  --{art} PATH".ljust(22) + f"{ARTIFACT_FILE[art]} (NIfTI){opt}")
    if needs_echo:
        lines += ["", "Acquisition parameters — give a params.json OR the flags (either works):",
                  "  --params PATH".ljust(22) + "params.json (or a BIDS phase sidecar)",
                  "  --te SEC [SEC ...]".ljust(22) + "echo times, seconds   [required here]",
                  "  --field-strength T".ljust(22) + "B0 in tesla   [required here]",
                  "  --b0-dir X Y Z".ljust(22) + "unit B0 direction (default: 0 0 1)",
                  "  --voxel-size X Y Z".ljust(22) + "mm (default: from the input header)"]
    else:
        # BFR/dipole take a field already in ppm — echo times and field strength don't enter the
        # maths (the dipole kernel depends only on B0 direction + voxel size), so all of these are
        # optional with sane defaults; a bare run works.
        lines += ["", "Acquisition parameters (optional — a ppm field; echo times / field strength aren't used):",
                  "  --b0-dir X Y Z".ljust(22) + "unit B0 direction (default: 0 0 1)",
                  "  --voxel-size X Y Z".ljust(22) + "mm (default: from the input header)",
                  "  --params PATH".ljust(22) + "params.json or a BIDS sidecar (optional)"]
    img_inputs = [a for a in consumes if a != "params"]
    req_imgs = [a for a in img_inputs if a not in OPTIONAL_ARTIFACTS or img_inputs == [a]]
    example = " ".join(f"--{a} {a}.nii.gz" for a in req_imgs)
    if needs_echo:
        example += " --te 0.004 0.012 0.02 0.028 --field-strength 7"
    if len(prods) == 1:
        lines += ["", "Output:",
                  "  -o PATH".ljust(22) + f"where to write {produced}.nii.gz "
                  f"(default: ./{produced}.nii.gz; a directory is fine)",
                  "",
                  f"Example:  qsm-ci run {slug} {example}",
                  f"Add  --truth {produced}.nii.gz  [--seg dseg.nii.gz]  to score the output."]
    else:
        outs = ", ".join(f"{p}.nii.gz" for p in prods)
        lines += ["", "Output:",
                  "  -o DIR".ljust(22) + f"directory to write {outs} into (default: current dir)",
                  "",
                  f"Example:  qsm-ci run {slug} {example} -o out/",
                  f"Add  --truth GT_DIR/  (a folder holding {outs}) to score each output."]
    lines.append(f"See   qsm-ci run {slug} --help  for runner/scoring options and method parameters.")
    return "\n".join(lines)


def list_command(argv=None, log=print) -> int:
    """`qsm-ci list` — show the reference algorithms available to run."""
    log(_algorithms_help())
    return 0


def _score(recon: Path, artifact: str, truth: Path, mask: Path, seg: "Path | None") -> dict:
    from . import qsm_eval
    kind = ARTIFACT_KIND[artifact]
    r, t, m = qsm_eval.load(recon), qsm_eval.load(truth), qsm_eval.load(mask)
    if r.shape != t.shape or r.shape != m.shape:
        raise SystemExit(f"shape mismatch: recon {r.shape}, truth {t.shape}, mask {m.shape}")
    if kind == "chisep":
        import numpy as np
        component = {"chi-para": "para", "chi-dia": "dia"}.get(artifact, "para")
        segd = np.rint(qsm_eval.load(seg)).astype("int32") if (seg and Path(seg).exists()) else None
        return qsm_eval.chisep_metrics(r, t, m, segd, component)
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
    consumes = _consumes(algo)
    prods = STAGES[stage]["produces"]
    produced = prods[0]
    desc = f"{algo['name']} — {stage} stage  ({', '.join(consumes)} → {', '.join(prods)})"
    if algo.get("description"):
        desc += "\n\n" + " ".join(str(algo["description"]).split())
    p = argparse.ArgumentParser(
        prog=f"qsm-ci run {slug}", description=desc,
        epilog=_manifest_epilog(algo), formatter_class=_HelpFmt)
    p.add_argument("slug", help=argparse.SUPPRESS)  # already known; keep argparse happy
    # An artifact that's normally optional (magnitude/phase) becomes required when it is the stage's
    # sole image input — the stage can't run without it (e.g. brain-extraction, which reads only the
    # magnitude). Elsewhere magnitude stays optional (MEDI opts into it; plain TKD ignores it).
    img_inputs = [a for a in consumes if a != "params"]
    for art in consumes:
        if art == "params":
            p.add_argument("--params", metavar="PATH", required=False,
                           help="params.json or a BIDS MEGRE sidecar — or use the acquisition flags below")
            continue
        req = art not in OPTIONAL_ARTIFACTS or img_inputs == [art]
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
    if len(prods) == 1:
        p.add_argument("-o", "--out", metavar="PATH", default=f"{produced}.nii.gz",
                       help="where to write the produced artifact (a file, or a directory)")
        p.add_argument("--truth", metavar="PATH", help=f"ground-truth {produced} to score against")
    else:
        outs = ", ".join(f"{a}.nii.gz" for a in prods)
        p.add_argument("-o", "--out", metavar="DIR", default=".",
                       help=f"directory to write the produced artifacts into ({outs})")
        p.add_argument("--truth", metavar="DIR",
                       help=f"ground-truth directory holding {outs} to score each output against")
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
    artifact_flags = {f"--{art}" for art in _consumes(algo)}
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
    consumes = _consumes(algo)
    prods = STAGES[stage]["produces"]
    multi = len(prods) > 1

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
                        log("  params (from BIDS sidecar): " + _params_summary(params, stage))
                    else:
                        shutil.copy(src, dest)  # already a params.json — use verbatim
                else:
                    params = _params_dict(args, stage)
                    dest.write_text(json.dumps(params, indent=2) + "\n")
                    log("  params: " + _params_summary(params, stage))
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

        # Copy every produced artifact out. Single-output stages honour `-o <file>` (a directory is
        # also accepted); a multi-output stage (χ-separation) always writes each canonical file into
        # the `-o <dir>` directory.
        out_arg = Path(args.out)
        written = {}
        for art in prods:
            src = odir / ARTIFACT_FILE[art]
            if not src.exists():
                raise SystemExit(f"submission did not write {ARTIFACT_FILE[art]} to /output")
            dest = out_arg / ARTIFACT_FILE[art] if (multi or out_arg.is_dir()) else out_arg
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dest)
            written[art] = dest
            log(f"✓ wrote {dest}  ({runtime:.1f}s)")

        if args.truth:
            # Single output: `--truth <file>` (a directory is also accepted). Multi-output: `--truth
            # <dir>` holding each ground-truth by canonical name; score every produced artifact.
            truth = Path(args.truth)
            for art in prods:
                tpath = truth / ARTIFACT_FILE[art] if (multi or truth.is_dir()) else truth
                metrics = _score(written[art], art, tpath, Path(args.mask), args.seg)
                _print_metrics(algo["name"], stage, art, runtime, metrics, log)
        else:
            log("  (no --truth given → not scored)")
    return 0
