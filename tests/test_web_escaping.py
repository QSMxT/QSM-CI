"""Guard: contributor-authored data cannot inject markup into the site.

`algorithms/<slug>/algorithm.yml` is written by whoever submits a method. `scripts/gen_manifest.py`
copies its `name`, `description`, `citation`, `code_url`, `ci_notes` and parameter documentation
verbatim into `web/algorithms.json`, which `web/js/viewer.js` renders into `innerHTML` on the
submission page. Region labels arrive the same way from the Hub-hosted `regions.json`. So a merged
submission is untrusted input to every visitor's browser, and every interpolation of it has to be
escaped.

Two halves:

* the behavioural tests run the real escaping helpers under node, so they check what the browser
  will actually do rather than what the source looks like;
* the source guards pin the specific call sites that were unescaped, so a future edit cannot quietly
  reintroduce a raw `${a.description}`.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "web" / "js" / "viewer.js"
RESULTS = ROOT / "web" / "results.html"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not available")

# Anything that must not survive into rendered HTML: the tag delimiters, the ampersand that would
# otherwise let an entity through, and both quote characters (the helpers are used inside
# attribute values, where &<> alone would not close the hole).
HOSTILE = "<img src=x onerror=alert(1)>\" onclick='alert(2)' & done"


def _node(script: str) -> dict:
    """Run `script` under node and parse the single JSON object it prints."""
    out = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, cwd=ROOT, timeout=60
    )
    assert out.returncode == 0, f"node failed:\n{out.stderr}"
    return json.loads(out.stdout)


def _viewer_helpers(calls: str) -> dict:
    """Evaluate viewer.js's escaping helpers in isolation and report `calls`.

    viewer.js is a browser script that touches the DOM, so it cannot simply be imported. The three
    helpers are self-contained `const` statements, so lift them out by name and evaluate just those.
    """
    return _node(
        """
        const fs = require("fs");
        const src = fs.readFileSync("web/js/viewer.js", "utf8");
        const grab = (name) => {
          const i = src.indexOf("const " + name + " =");
          if (i < 0) throw new Error("helper not found in viewer.js: " + name);
          const m = src.slice(i).match(/^[\\s\\S]*?\\n(?=(const |function |\\/\\/))/);
          if (!m) throw new Error("could not delimit helper: " + name);
          return m[0];
        };
        const defs = ["escapeHtml", "safeUrl", "withName"].map(grab).join("");
        const { escapeHtml, safeUrl, withName } =
          new Function(defs + "\\nreturn { escapeHtml, safeUrl, withName };")();
        console.log(JSON.stringify(%s));
        """
        % calls
    )


def _results_esc(calls: str) -> dict:
    """Evaluate results.html's `_esc` in isolation and report `calls`."""
    return _node(
        """
        const fs = require("fs");
        const src = fs.readFileSync("web/results.html", "utf8");
        const i = src.indexOf("_esc(s) {");
        if (i < 0) throw new Error("_esc not found in results.html");
        const body = src.slice(i).match(/^_esc\\(s\\) \\{[\\s\\S]*?\\n?\\s*\\},/);
        if (!body) throw new Error("could not delimit _esc");
        const obj = new Function("return { " + body[0] + " };")();
        const _esc = obj._esc.bind(obj);
        console.log(JSON.stringify(%s));
        """
        % calls
    )


# --------------------------------------------------------------------------------------
#  Behaviour
# --------------------------------------------------------------------------------------
@needs_node
def test_escape_html_neutralises_tags_and_both_quote_characters():
    got = _viewer_helpers('{ out: escapeHtml(%s) }' % json.dumps(HOSTILE))["out"]
    for ch in "<>\"'":
        assert ch not in got, f"escapeHtml left {ch!r} unescaped: {got}"
    assert "&amp;" in got, "escapeHtml must escape & or entities pass through"
    assert "onerror" in got, "escapeHtml must preserve the text, only neutralise the markup"


@needs_node
def test_escape_html_coerces_non_strings():
    """A YAML `default: 3` reaches the parameter table as a number, and `citation:` may be absent."""
    got = _viewer_helpers("{ n: escapeHtml(3), nul: escapeHtml(null), und: escapeHtml(undefined) }")
    assert got == {"n": "3", "nul": "", "und": ""}


@needs_node
@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
        "/relative/path",
        "",
    ],
)
def test_safe_url_rejects_everything_that_is_not_absolute_http(url):
    assert _viewer_helpers("{ out: safeUrl(%s) }" % json.dumps(url))["out"] == ""


@needs_node
@pytest.mark.parametrize("url", ["https://github.com/a/b", "http://example.org/x?y=1#z"])
def test_safe_url_keeps_ordinary_links(url):
    assert _viewer_helpers("{ out: safeUrl(%s) }" % json.dumps(url))["out"].startswith(url[:20])


@needs_node
def test_safe_url_encodes_a_doi_that_tries_to_break_out_of_the_attribute():
    got = _viewer_helpers(
        '{ out: safeUrl("https://doi.org/" + %s) }' % json.dumps('10.1/x" onclick="alert(1)')
    )["out"]
    assert '"' not in got and " " not in got, got
    assert got.startswith("https://doi.org/10.1/x")


@needs_node
def test_with_name_is_literal_and_escaped():
    """`String.replace` expands `$&` in a string replacement; a method name is not a pattern."""
    got = _viewer_helpers(
        '{ dollar: withName("<span>%%NAME%%</span>", %s), tag: withName("<span>%%NAME%%</span>", %s) }'
        % (json.dumps("A $& B"), json.dumps("<b>x</b>"))
    )
    assert got["dollar"] == "<span>A $&amp; B</span>", got["dollar"]
    assert got["tag"] == "<span>&lt;b&gt;x&lt;/b&gt;</span>", got["tag"]


@needs_node
def test_results_esc_covers_quotes_because_it_is_used_inside_attributes():
    got = _results_esc('{ out: _esc(%s), nul: _esc(null) }' % json.dumps(HOSTILE))
    for ch in "<>\"'":
        assert ch not in got["out"], f"_esc left {ch!r} unescaped: {got['out']}"
    assert got["nul"] == ""


# --------------------------------------------------------------------------------------
#  Source guards
# --------------------------------------------------------------------------------------
# Manifest fields that reached innerHTML raw. Each must now appear only inside an escaping call.
RAW_INTERPOLATIONS = [
    "${a.name}",
    "${a.description || \"\"}",
    "${a.citation || \"\"}",
    "${a.code_url}",
    "${zdoi.url}",
    "${p.name}",
    "${p.default}",
    "${p.description || \"\"}",
    "`<li>${n}</li>`",
    "${block.labels[r.k] || \"label-\" + r.k}",
    "${block.labels[k] || \"label-\" + k}",
]


@pytest.mark.parametrize("frag", RAW_INTERPOLATIONS)
def test_manifest_fields_are_not_interpolated_raw(frag):
    # Compare a bool, not the file: asserting `frag not in text` makes pytest dump all of viewer.js.
    present = frag in VIEWER.read_text()
    assert not present, (
        f"{frag} is interpolated into innerHTML without escaping; "
        "wrap it in escapeHtml() (see the module docstring)"
    )


def test_every_run_row_name_goes_through_with_name():
    """The `%NAME%` placeholder is substituted in exactly one place, which escapes."""
    src = VIEWER.read_text()
    assert '.replace("%NAME%"' not in src.replace(
        'const withName = (html, name) => html.replace("%NAME%"', ""
    ), "a run row still substitutes %NAME% directly instead of calling withName()"
    assert src.count("%NAME%") == 3, "expected the withName definition plus the two row templates"


def test_hrefs_in_the_method_card_are_scheme_checked():
    """No `href="` in viewer.js may interpolate a manifest value without going through safeUrl."""
    src = VIEWER.read_text()
    for m in re.finditer(r'href="\$\{([^}]*)\}"', src):
        expr = m.group(1)
        assert "safeUrl" in expr or "escapeHtml" in expr, (
            f'href interpolates {expr!r} unchecked; run it through safeUrl() first'
        )
