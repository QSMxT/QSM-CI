"""Shared fixtures for the test suite.

`pipeline` loads scripts/pipeline.py ONCE per session as a module object. It is a standalone script
(no package), so the test files used to each exec it from its file path — three distinct module
objects, three `sys.path.insert(0, ROOT)` side effects. scripts/ is on sys.path for the session via
pyproject's `[tool.pytest.ini_options] pythonpath`, so a plain import resolves it, and `sys.modules`
caching means every consumer shares the same object.
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture(scope="session")
def pipeline():
    """scripts/pipeline.py as a module (the composed/isolated scorer's functions and tables)."""
    return importlib.import_module("pipeline")
