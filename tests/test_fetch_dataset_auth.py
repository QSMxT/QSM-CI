"""scripts/fetch_dataset.sh: OSF authentication.

The harmonization project (gkemr) is public now but is going private until its data are released, so
the fetch must work both ways: tokenless while it is public, authenticated whenever a token is set,
and with a clear error (not an HTML sign-in page unpacked as a zip) when a private file is fetched
without access. `curl` is replaced by a stub that logs its arguments and plays back scripted hops,
so nothing here touches the network.
"""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
FID = "6a8c5227ebd554439fff2010"

# The stub answers by URL: a line "<url-prefix>|<http code>|<redirect url>|<body>" per hop ('|', not a
# tab: `read` collapses runs of a whitespace IFS, which would shift an empty redirect field).
CURL_STUB = r'''#!/usr/bin/env bash
out=""; url=""; fmt=""; args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
  case "${args[$i]}" in
    -o) out="${args[$((i+1))]}" ;;
    -w) fmt="${args[$((i+1))]}" ;;
    -H) ;;
    https://*) url="${args[$i]}" ;;
  esac
done
printf '%s\n' "$*" >> "$CURL_LOG"
while IFS='|' read -r prefix code redirect body; do
  if [[ "$url" == "$prefix"* ]]; then
    printf '%s' "$body" > "$out"
    if [[ "$fmt" == *redirect_url* ]]; then printf '%s %s' "$code" "$redirect"; else printf '%s' "$code"; fi
    exit 0
  fi
done < "$CURL_SCRIPT"
echo "stub: no scripted answer for $url" >&2; exit 7
'''


@pytest.fixture
def fetch(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy(ROOT / "scripts" / "fetch_dataset.sh", scripts)
    (scripts / "pack_dataset.py").write_text("raise SystemExit('not used')\n")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "curl").write_text(CURL_STUB)
    (bindir / "curl").chmod(0o755)

    def run(entry: dict, hops: list, token: "str | None", hf_token: "str | None" = None):
        (scripts / "datasets.json").write_text(json.dumps({"x": {"prepacked": True, **entry}}))
        (tmp_path / "hops.tsv").write_text("".join("|".join(h) + "\n" for h in hops))
        log = tmp_path / "curl.log"
        log.unlink(missing_ok=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith("OSF_")}
        env.update(PATH=f"{bindir}:{env['PATH']}", CURL_LOG=str(log),
                   CURL_SCRIPT=str(tmp_path / "hops.tsv"), OSF_ZIP=str(tmp_path / "dl.zip"))
        env.pop("HF_TOKEN", None)
        if token is not None:
            env["OSF_TOKEN"] = token
        if hf_token is not None:
            env["HF_TOKEN"] = hf_token
        p = subprocess.run(["bash", str(scripts / "fetch_dataset.sh"), "x", str(tmp_path / "out")],
                           env=env, capture_output=True, text=True)
        calls = log.read_text().splitlines() if log.exists() else []
        return p, calls, tmp_path / "dl.zip"
    return run


PUBLIC = {"osf_file": FID, "osf_project": "gkemr", "osf_public": True}
STORAGE = "https://storage.example/signed?x=1"


def test_public_without_token_uses_the_anonymous_endpoint(fetch):
    p, calls, _ = fetch(PUBLIC, [(f"https://osf.io/download/{FID}/", "302", STORAGE, ""),
                                 (STORAGE, "200", "", "zipbytes")], token=None)
    assert calls[0].endswith(f"https://osf.io/download/{FID}/")
    assert not any("Authorization" in c for c in calls)
    # (the fake body is no zip, so the unzip after the download fails; the download is what is tested)
    assert "downloading gkemr/" in p.stdout


def test_public_with_token_downloads_authenticated(fetch):
    wb = f"https://files.osf.io/v1/resources/gkemr/providers/osfstorage/{FID}"
    p, calls, _ = fetch(PUBLIC, [(wb, "302", STORAGE, ""), (STORAGE, "200", "", "zipbytes")],
                        token="tok")
    assert calls[0].endswith(wb) and "Authorization: Bearer tok" in calls[0]
    # The pre-signed storage URL rejects an Authorization header, so the token never reaches it.
    assert STORAGE in calls[1] and "Authorization" not in calls[1]


def test_private_file_without_token_fails_clearly(fetch):
    login = f"https://accounts.osf.io/login?service=https%3A%2F%2Fosf.io%2Fdownload%2F{FID}%2F"
    p, calls, zip_path = fetch(PUBLIC, [(f"https://osf.io/download/{FID}/", "302", login, "")],
                               token=None)
    assert p.returncode == 1
    assert "sign-in page" in p.stderr and "no OSF_TOKEN was set" in p.stderr
    assert len(calls) == 1          # the sign-in page itself is never downloaded
    assert not zip_path.exists()    # nothing left for a cache to save


def test_token_without_access_fails_clearly(fetch):
    wb = f"https://files.osf.io/v1/resources/gkemr/providers/osfstorage/{FID}"
    p, _, zip_path = fetch(PUBLIC, [(wb, "403", "", "forbidden")], token="tok")
    assert p.returncode == 1
    assert "HTTP 403" in p.stderr and "no read access" in p.stderr
    assert not zip_path.exists()


def test_unflagged_private_entry_needs_a_token(fetch):
    p, calls, _ = fetch({"osf_file": FID}, [], token=None)
    assert p.returncode == 1 and "private OSF project" in p.stderr
    assert calls == []


HF_URL = "https://huggingface.co/datasets/qsmxt/x/resolve/main/qsmci-inputs/a.zip"
WB_PRIV = f"https://files.osf.io/v1/resources/vkyr2/providers/osfstorage/{FID}"
PRIVATE_HF = {"osf_file": FID, "osf_project": "vkyr2", "osf_public": False,
              "hf_repo": "qsmxt/x", "hf_path": "qsmci-inputs/a.zip",
              "sha256": hashlib.sha256(b"zipbytes").hexdigest()}


def test_hf_copy_is_tried_first_with_a_token(fetch):
    p, calls, _ = fetch(PRIVATE_HF, [(HF_URL, "200", "", "zipbytes")], token="osf", hf_token="hft")
    assert len(calls) == 1 and HF_URL in calls[0] and "Authorization: Bearer hft" in calls[0]
    assert "-L" in calls[0].split() or "-sSL" in calls[0].split()
    assert "sha256 mismatch" not in p.stderr and "from Hugging Face" in p.stdout


def test_hf_refusal_falls_back_to_osf(fetch):
    p, calls, _ = fetch(PRIVATE_HF, [(HF_URL, "401", "", "nope"), (WB_PRIV, "302", STORAGE, ""),
                                     (STORAGE, "200", "", "zipbytes")], token="osf", hf_token="bad")
    assert HF_URL in calls[0] and WB_PRIV in calls[1] and "Authorization: Bearer osf" in calls[1]
    assert "falling back to OSF" in p.stderr and "sha256 mismatch" not in p.stderr


def test_no_hf_token_goes_straight_to_osf(fetch):
    p, calls, _ = fetch(PRIVATE_HF, [(WB_PRIV, "302", STORAGE, ""), (STORAGE, "200", "", "zipbytes")],
                        token="osf")
    assert not any("huggingface" in c for c in calls) and "no HF_TOKEN" in p.stderr


def test_no_token_at_all_names_both(fetch):
    p, calls, _ = fetch(PRIVATE_HF, [], token=None)
    assert p.returncode == 1 and "HF_TOKEN" in p.stderr and "OSF_TOKEN" in p.stderr and calls == []


def test_sha256_mismatch_is_rejected(fetch):
    p, _, zip_path = fetch(PRIVATE_HF, [(HF_URL, "200", "", "tampered")], token=None, hf_token="hft")
    assert p.returncode == 1 and "sha256 mismatch" in p.stderr and not zip_path.exists()


def _fetch_steps():
    for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        doc = yaml.safe_load(wf.read_text())
        for job_id, job in (doc.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                if "fetch_dataset.sh" in str(step.get("run", "")):
                    yield f"{wf.name}:{job_id}:{step.get('name', '?')}", step


def test_every_fetch_step_gets_the_osf_token():
    """A step that fetches without OSF_TOKEN works only while its project is public: once gkemr is
    private it would fail. Every fetch passes the secret, whatever project it reads today."""
    steps = list(_fetch_steps())
    assert steps, "no workflow step runs fetch_dataset.sh — has it been renamed?"
    missing = [where for where, step in steps
               if (step.get("env") or {}).get("OSF_TOKEN") != "${{ secrets.OSF_TOKEN }}"]
    assert not missing, f"fetch steps without OSF_TOKEN: {missing}"


def test_every_fetch_step_gets_the_hf_token():
    """The EMTP inputs' primary copy is a private Hugging Face dataset; without HF_TOKEN a fetch falls
    back to OSF, which goes read-only in 2027 and will eventually drop private projects."""
    want = "${{ secrets.HF_READ_TOKEN || secrets.HF_TOKEN }}"
    missing = [where for where, step in _fetch_steps() if (step.get("env") or {}).get("HF_TOKEN") != want]
    assert not missing, f"fetch steps without HF_TOKEN: {missing}"
