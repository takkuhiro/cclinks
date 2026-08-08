"""Test-wide setup.

The suite must not care whether fzf happens to be installed on the machine
running it. Every test therefore starts from "fzf is absent", and the few that
exercise the picker say so explicitly. Without this, a developer with fzf on
their PATH gets a green run while CI, which has none, goes red.
"""

import pytest

from cclinks import cli


@pytest.fixture(autouse=True)
def no_fzf_on_path(monkeypatch):
    monkeypatch.setattr(cli, "_FZF_FALLBACKS", ())
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)
