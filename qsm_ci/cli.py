"""qsm-ci — command-line companion for the QSM-CI challenge.

  qsm-ci new                 scaffold a submission folder (interactive)
  qsm-ci run <slug> ...      run one stage on explicit input files; score it with --truth
  qsm-ci submit <slug>       open a pull request adding your submission
  qsm-ci doctor              check your environment

`run` takes flags for the artifacts its stage consumes, e.g.
  qsm-ci run tkd --localfield lf.nii.gz --mask mask.nii.gz --params params.json --truth chi.nii.gz
See `qsm-ci run <slug> --help` for the exact flags a submission needs.
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

    # `run` parses its own (stage-dependent) flags — register it just for help/usage listing.
    sub.add_parser("run", add_help=False,
                   help="run one stage on explicit files (qsm-ci run <slug> --help for flags)")

    s = sub.add_parser("submit", help="open a pull request adding your submission")
    s.add_argument("slug")
    s.set_defaults(func=_cmd_submit)

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

    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
