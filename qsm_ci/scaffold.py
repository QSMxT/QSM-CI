"""`qsm-ci new` — scaffold a submission folder (the terminal version of the web Submit wizard)."""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

from . import templates
from .stages import STAGES

STAGE_HELP = {
    "dipole": "local field → susceptibility (χ)",
    "bfr": "total field → local field",
    "field-mapping": "multi-echo phase → total field",
    "end-to-end": "phase → χ (single-step)",
    "bfr+dipole": "total field → χ",
    "unwrap+bfr": "phase → local field",
}


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "my-method"


def _ask(prompt: str, default: str = "", choices=None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        ans = input(f"{prompt}{suffix}: ").strip() or default
        if choices and ans not in choices:
            print(f"  choose one of: {', '.join(choices)}")
            continue
        return ans


def interactive() -> dict:
    print("Let's scaffold a QSM-CI submission.\n")
    print("Stages:")
    for k in STAGES:
        print(f"  {k:<14} {STAGE_HELP.get(k, '')}")
    stage = _ask("\nstage", "dipole", list(STAGES))
    name = _ask("name", "My Method")
    slug = _ask("slug (folder name)", slugify(name))
    print(f"\nLanguages: {', '.join(templates.LANGS)}")
    lang = _ask("language", "python", list(templates.LANGS))
    image = _ask("container image", "ghcr.io/you/your-image:v1")
    authors = _ask("authors (comma-separated, optional)", "")
    return {
        "stage": stage, "name": name, "slug": slug, "lang": lang, "image": image,
        "authors": [a.strip() for a in authors.split(",") if a.strip()],
        "description": "", "citation": None, "doi": None, "code_url": None,
        "license": "MIT", "run": "bash run.sh", "params": [],
    }


def write_submission(meta: dict, dest_root: Path, force: bool = False) -> Path:
    dest = dest_root / meta["slug"]
    if dest.exists() and not force:
        raise SystemExit(f"{dest} already exists (use --force to overwrite)")
    dest.mkdir(parents=True, exist_ok=True)
    for fname, body in templates.files(meta):
        (dest / fname).write_text(body)
        if fname == "run.sh":
            p = dest / fname
            p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return dest


def run_new(args) -> int:
    if args.name and args.stage:
        meta = {
            "stage": args.stage, "name": args.name,
            "slug": args.slug or slugify(args.name), "lang": args.lang,
            "image": args.image or "ghcr.io/you/your-image:v1",
            "authors": [], "description": "", "citation": None, "doi": None,
            "code_url": None, "license": "MIT", "run": "bash run.sh", "params": [],
        }
    else:
        meta = interactive()

    # default into ./algorithms/ if it exists (repo checkout), else the current dir
    root = Path(args.dir) if args.dir else (Path("algorithms") if Path("algorithms").is_dir() else Path("."))
    dest = write_submission(meta, root, force=args.force)
    rel = os.path.relpath(dest)
    print(f"\n✓ created {rel}/")
    for fname, _ in templates.files(meta):
        print(f"    {rel}/{fname}")
    print(f"\nNext:  edit your reconstruction, then  qsm-ci run {meta['slug']} --help")
    return 0
