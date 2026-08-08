"""The version must be written down in exactly one place.

pyproject holds it; the package reads it back from installed metadata. This
guards against the two drifting apart, which is what happened when the module
carried a literal of its own.
"""

import re
from pathlib import Path

import cclinks

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def declared_version() -> str:
    for line in PYPROJECT.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r'version\s*=\s*"([^"]+)"', line.strip())
        if match:
            return match.group(1)
    raise AssertionError("no version found in pyproject.toml")


def test_package_version_matches_pyproject():
    assert cclinks.__version__ == declared_version()


def test_version_looks_like_a_release():
    assert re.fullmatch(r"\d+\.\d+\.\d+", declared_version())
