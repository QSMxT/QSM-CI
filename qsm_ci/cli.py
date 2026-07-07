"""qsm-ci — command-line companion for the QSM-CI challenge.

  qsm-ci new                 scaffold a submission folder (interactive)
  qsm-ci test <slug>         run it on the dev phantom and print your scores
  qsm-ci fetch               download/refresh the dev phantom
  qsm-ci submit <slug>       open a pull request adding your submission
  qsm-ci doctor              check your environment
"""

from __future__ import annotations

import argparse
import sys

from . import __version__


def _cmd_new(args) -> int:
    from .scaffold import run_new
    return run_new(args)


def _cmd_test(args) -> int:
    from .runner import test_algorithm, check_docker
    if args.runner == "docker" and not check_docker():
        print("! Docker isn't available. Install/start Docker, or use --runner local "
              "(runs run.sh on the host; needs your deps installed).", file=sys.stderr)
        return 1
    try:
        test_algorithm(args.slug, runner=args.runner)
    except SystemExit as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_fetch(args) -> int:
    from . import data
    ds = data.ensure_dataset(force=args.force)
    print(f"dev phantom: {ds}")
    return 0


def _cmd_submit(args) -> int:
    from .submit import run_submit
    return run_submit(args)


def _cmd_doctor(args) -> int:
    import shutil
    from .runner import check_docker
    print(f"qsm-ci {__version__}")
    print(f"  docker   {'ok' if check_docker() else 'MISSING (needed for qsm-ci test)'}")
    print(f"  gh       {'ok' if shutil.which('gh') else 'missing (optional, for qsm-ci submit)'}")
    for mod in ("numpy", "scipy", "nibabel"):
        try:
            __import__(mod)
            print(f"  {mod:<8} ok")
        except ImportError:
            print(f"  {mod:<8} MISSING (needed for scoring)")
    try:
        from . import data
        print(f"  dataset  {data.ensure_dataset()}")
    except SystemExit as e:
        print(f"  dataset  not available ({e})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="qsm-ci", description="Submit and test QSM-CI reconstructions.")
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

    t = sub.add_parser("test", help="run a submission on the dev phantom and score it")
    t.add_argument("slug", help="submission slug or path to its folder")
    t.add_argument("--runner", choices=["docker", "local"], default="docker")
    t.set_defaults(func=_cmd_test)

    f = sub.add_parser("fetch", help="download/refresh the dev phantom")
    f.add_argument("--force", action="store_true")
    f.set_defaults(func=_cmd_fetch)

    s = sub.add_parser("submit", help="open a pull request adding your submission")
    s.add_argument("slug")
    s.set_defaults(func=_cmd_submit)

    d = sub.add_parser("doctor", help="check your environment")
    d.set_defaults(func=_cmd_doctor)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
