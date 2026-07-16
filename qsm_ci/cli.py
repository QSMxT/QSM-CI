"""qsm-ci — command-line companion for the QSM-CI challenge.

  qsm-ci list                list the reference algorithms you can run
  qsm-ci new                 scaffold a submission folder (interactive)
  qsm-ci run <slug> ...      run one stage on explicit input files; score it with --truth
  qsm-ci submit <slug>       open a pull request adding your submission
  qsm-ci doctor              check your environment

Start with `qsm-ci list` to see the slugs, then `qsm-ci run <slug>` to see the inputs that
slug's stage needs. `run` takes a flag per consumed artifact, e.g.
  qsm-ci run tkd --localfield lf.nii.gz --mask mask.nii.gz --params params.json --truth chi.nii.gz
"""

from __future__ import annotations

import argparse
import sys

from . import __version__


def _cmd_new(args) -> int:
    from .scaffold import run_new
    return run_new(args)


def _cmd_submit(args) -> int:
    from .submit import run_submit
    return run_submit(args)


def _cmd_interface(args) -> int:
    from .interfaces import generate, generate_pipeline
    try:
        if args.pipeline:
            text = generate_pipeline(args.engine, [s.strip() for s in args.pipeline.split(",")])
        else:
            text = generate(args.engine, stage=args.stage, slug=args.slug)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(text)
        print(f"wrote {args.engine} wrapper → {args.out}")
    else:
        print(text, end="")
    return 0


def _cmd_doctor(args) -> int:
    import shutil
    from .runner import check_runner
    print(f"qsm-ci {__version__}")
    engines = [r for r in ("docker", "podman", "apptainer") if check_runner(r)]
    print(f"  runners  {', '.join(engines) if engines else 'none'} + local  "
          f"(qsm-ci run --runner …)")
    print(f"  gh       {'ok' if shutil.which('gh') else 'missing (optional, for qsm-ci submit)'}")
    for mod in ("numpy", "scipy", "nibabel"):
        try:
            __import__(mod)
            print(f"  {mod:<8} ok")
        except ImportError:
            print(f"  {mod:<8} MISSING (needed for --truth scoring)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="qsm-ci", description="Submit and run QSM-CI reconstructions.")
    p.add_argument("--version", action="version", version=f"qsm-ci {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="scaffold a submission folder")
    n.add_argument("--stage")
    n.add_argument("--name")
    n.add_argument("--slug")
    n.add_argument("--lang", default="python")
    n.add_argument("--image")
    n.add_argument("--dir", help="where to create the folder (default: ./algorithms or .)")
    n.add_argument("--force", action="store_true")
    n.set_defaults(func=_cmd_new)

    sub.add_parser("list", help="list the reference algorithms you can run")

    # `run` parses its own (stage-dependent) flags — register it just for help/usage listing.
    sub.add_parser("run", add_help=False,
                   help="run one stage on explicit files (qsm-ci run <slug> for the inputs it needs)")

    s = sub.add_parser("submit", help="open a pull request adding your submission")
    s.add_argument("slug")
    s.set_defaults(func=_cmd_submit)

    i = sub.add_parser("interface",
                       help="generate a workflow-engine wrapper (cwl/snakemake/nextflow)")
    i.add_argument("engine", choices=["cwl", "snakemake", "nextflow"])
    i.add_argument("--stage", help="one stage/span (default: field-mapping, bfr, dipole)")
    i.add_argument("--slug", default="SLUG", help="default method slug baked into the wrapper")
    i.add_argument("--pipeline", metavar="FM,BFR,DIPOLE",
                   help="emit a chained end-to-end pipeline: 3 method slugs (field-mapping,bfr,dipole)")
    i.add_argument("-o", "--out", help="write to this file (default: stdout)")
    i.set_defaults(func=_cmd_interface)

    d = sub.add_parser("doctor", help="check your environment")
    d.set_defaults(func=_cmd_doctor)
    return p


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # `run` has dynamic, stage-derived flags — dispatch it before argparse sees the unknown flags.
    if argv and argv[0] == "run":
        from .runner import run_command
        try:
            return run_command(argv[1:])
        except SystemExit as e:
            if isinstance(e.code, int):
                return e.code
            print(f"✗ {e}", file=sys.stderr)
            return 1

    if argv and argv[0] == "list":
        from .runner import list_command
        return list_command(argv[1:])

    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
