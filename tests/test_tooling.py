"""Tests that keep the repo's tooling pins consistent with each other."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRE_COMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"
REQUIREMENTS_DEV = REPO_ROOT / "requirements_dev.txt"


def _hook_rev(repo_url: str) -> str:
    """Return the `rev` pinned for a repo in .pre-commit-config.yaml."""
    text = PRE_COMMIT_CONFIG.read_text(encoding="utf-8")
    match = re.search(rf"- repo: {re.escape(repo_url)}\s*\n\s*rev:\s*(\S+)", text)
    assert match, f"{repo_url} not found in .pre-commit-config.yaml"
    return match.group(1)


def _requirement_pin(package: str) -> str:
    """Return the `==` pin for a package in requirements_dev.txt."""
    text = REQUIREMENTS_DEV.read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(package)}==(\S+)", text, re.MULTILINE)
    assert match, f"{package} has no == pin in requirements_dev.txt"
    return match.group(1)


def test_ruff_hook_matches_dev_requirement():
    """The prek ruff hook and .venv's ruff are the same version.

    Dependabot bumps requirements_dev.txt but not the hook's `rev`, so
    without this check `make check` (.venv ruff) and the commit hook / CI
    (prek ruff) silently drift apart and can disagree on lint or format.
    A bump PR now fails here until the hook is bumped alongside it.
    """
    hook = _hook_rev("https://github.com/astral-sh/ruff-pre-commit").removeprefix("v")
    assert hook == _requirement_pin("ruff")
