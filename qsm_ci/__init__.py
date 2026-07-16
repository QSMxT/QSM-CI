"""qsm-ci — command-line companion for the QSM-CI reconstruction challenge.

Scaffold a submission (`qsm-ci new`), run one stage on explicit input files and score it
(`qsm-ci run ... --truth`), and open a pull request (`qsm-ci submit`). The scorer is the exact
same code the challenge CI runs (`qsm_ci.qsm_eval`), so local numbers match the leaderboard.
"""

# Version is baked into the wheel by setuptools-scm (from the git tag) at build time; read it back
# from the installed metadata so `qsm-ci --version` matches the release. Fallback for a source tree
# with no metadata (e.g. running from an unbuilt checkout).
try:
    from importlib.metadata import PackageNotFoundError, version as _pkg_version

    __version__ = _pkg_version("qsm-ci")
except PackageNotFoundError:
    __version__ = "0+unknown"
