#!/usr/bin/env python3
"""Mirror the Ridani et al. OSF project 9xwhz (Susceptibility-Separation-Phantom
paper data) to a local directory, preserving the folder structure.

Resumable: files whose size already matches the OSF-reported size are skipped.
Writes a manifest (path, size, md5-from-OSF) to <dest>/osf_manifest.tsv so the
mirror can be integrity-checked and later cited as the bit-for-bit reference.

Usage: python3 scripts/mirror_ridani_osf.py [dest]   (default data/ridani-osf)
"""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

PROJECT = "9xwhz"
ROOT = f"https://api.osf.io/v2/nodes/{PROJECT}/files/osfstorage/?page%5Bsize%5D=100"


def api(url):
    with urllib.request.urlopen(url) as r:
        return json.load(r)


def walk(url):
    while url:
        d = api(url)
        for f in d["data"]:
            a = f["attributes"]
            if a["kind"] == "folder":
                yield from walk(
                    f["relationships"]["files"]["links"]["related"]["href"]
                    + "?page%5Bsize%5D=100"
                )
            else:
                yield {
                    "path": a["materialized_path"].lstrip("/"),
                    "size": a["size"],
                    "md5": (a.get("extra", {}).get("hashes") or {}).get("md5"),
                    "download": f["links"]["download"],
                }
        url = d["links"].get("next")


def main():
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else "data/ridani-osf")
    dest.mkdir(parents=True, exist_ok=True)
    files = list(walk(ROOT))
    total = sum(f["size"] for f in files)
    print(f"{len(files)} files, {total/1e9:.2f} GB total", flush=True)

    with open(dest / "osf_manifest.tsv", "w") as m:
        m.write("path\tsize\tmd5\n")
        for f in files:
            m.write(f"{f['path']}\t{f['size']}\t{f['md5']}\n")

    done = 0
    for f in files:
        out = dest / f["path"]
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists() and out.stat().st_size == f["size"]:
            done += f["size"]
            print(f"skip  {f['path']}", flush=True)
            continue
        tmp = out.with_suffix(out.suffix + ".part")
        for attempt in range(5):
            try:
                with urllib.request.urlopen(f["download"]) as r, open(tmp, "wb") as w:
                    h = hashlib.md5()
                    while chunk := r.read(1 << 20):
                        w.write(chunk)
                        h.update(chunk)
                ok = h.hexdigest() == f["md5"] if f["md5"] else tmp.stat().st_size == f["size"]
                if ok:
                    break
                print(f"retry {f['path']} (bad hash/size, attempt {attempt+1})", flush=True)
            except OSError as e:
                print(f"retry {f['path']} ({e}, attempt {attempt+1})", flush=True)
        else:
            raise RuntimeError(f"failed after retries: {f['path']}")
        tmp.rename(out)
        done += f["size"]
        print(f"ok    {f['path']} ({done/total*100:.0f}%)", flush=True)
    print("MIRROR COMPLETE", flush=True)


if __name__ == "__main__":
    main()
