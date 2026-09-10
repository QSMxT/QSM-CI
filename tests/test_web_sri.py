"""Guard: every third-party asset the site loads from a CDN is pinned AND subresource-integrity checked.

The pages under web/ load Alpine, highlight.js, KaTeX, uPlot and NiiVue from public CDNs. A pinned
version alone does not stop a compromised or mis-served CDN from running arbitrary script on the
leaderboard; `integrity="sha384-…"` (plus `crossorigin="anonymous"`, which SRI needs for cross-origin
fetches) does. A version bump that forgets to recompute the hash fails here rather than silently
dropping the check:

    curl -s <url> | openssl dgst -sha384 -binary | openssl base64 -A

Google Fonts is the one deliberate exception: its stylesheet is generated per user agent, so it has no
stable hash (and it is CSS, not script).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
HTML = sorted(WEB.glob("*.html"))
JS = sorted((WEB / "js").glob("*.js"))

TAG = re.compile(r"<(script|link)\b[^>]*>", re.I)
ATTR = re.compile(r"""\b([a-zA-Z-]+)\s*=\s*"([^"]*)\"""")
SRI = re.compile(r"^sha(256|384|512)-[A-Za-z0-9+/]+={0,2}$")
SRI_EXEMPT_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com")


def _remote_tags():
    """Yield (html file, tag text, attrs) for every <script>/<link> that points at another origin."""
    for html in HTML:
        for m in TAG.finditer(html.read_text()):
            attrs = dict(ATTR.findall(m.group(0)))
            url = attrs.get("src") or attrs.get("href") or ""
            if not url.startswith(("http://", "https://", "//")):
                continue
            if any(h in url for h in SRI_EXEMPT_HOSTS):
                continue
            yield html, m.group(0), attrs


def test_pages_have_remote_assets():
    # The guard is meaningless if the pattern stops matching (e.g. a markup restyle); pin that it sees
    # the CDN tags it is meant to protect.
    assert len(list(_remote_tags())) >= 6


def test_every_cdn_script_and_stylesheet_carries_integrity():
    problems = []
    for html, tag, attrs in _remote_tags():
        if attrs.get("rel", "").lower() == "preconnect":
            continue
        url = attrs.get("src") or attrs.get("href")
        if not re.search(r"@\d+\.\d+|/\d+\.\d+\.\d+/", url):
            problems.append(f"{html.name}: {url} is not version-pinned")
        if not SRI.match(attrs.get("integrity", "")):
            problems.append(f"{html.name}: {url} has no integrity= hash")
        if attrs.get("crossorigin", "").lower() != "anonymous":
            problems.append(f"{html.name}: {url} needs crossorigin=\"anonymous\" for SRI to apply")
    assert not problems, "\n".join(problems)


def test_es_module_imports_from_cdn_are_modulepreloaded_with_integrity():
    """An `import … from "https://…"` inside a module can't carry a hash itself. The page that loads the
    module must <link rel="modulepreload" href="<same url>" integrity=…> so the checked fetch is what
    the import resolves to; the two URLs must match exactly or the preload guards nothing."""
    preloads = {}
    for html, _, attrs in _remote_tags():
        if attrs.get("rel", "").lower() == "modulepreload":
            preloads[attrs["href"]] = (html.name, attrs.get("integrity", ""))
    imports = []
    for js in JS:
        for m in re.finditer(r"""^\s*import\b[^;]*?from\s+["'](https?://[^"']+)["']""", js.read_text(), re.M):
            imports.append((js.name, m.group(1)))
    assert imports, "expected at least the NiiVue import in web/js/viewer.js"
    for js_name, url in imports:
        assert url in preloads, f"{js_name} imports {url} but no web/*.html modulepreloads that exact URL with integrity="
        assert SRI.match(preloads[url][1]), f"{preloads[url][0]}: modulepreload for {url} has no integrity= hash"
