"""fzf discovery tests.

A launcher's PATH differs from an interactive shell's and often lacks Homebrew's
bin. Exiting quietly when fzf is missing hides the cause, so it must be reported.
"""

import pytest

from cclinks import cli


class TestFindFzf:
    def test_prefers_path_lookup(self, monkeypatch):
        monkeypatch.setattr(cli.shutil, "which", lambda name: "/usr/bin/fzf")
        assert cli.find_fzf() == "/usr/bin/fzf"

    def test_falls_back_to_known_locations(self, monkeypatch, tmp_path):
        monkeypatch.setattr(cli.shutil, "which", lambda name: None)
        candidate = tmp_path / "fzf"
        candidate.write_text("#!/bin/sh\n")
        candidate.chmod(0o755)
        monkeypatch.setattr(cli, "_FZF_FALLBACKS", (str(candidate),))
        assert cli.find_fzf() == str(candidate)

    def test_returns_none_when_absent(self, monkeypatch):
        monkeypatch.setattr(cli.shutil, "which", lambda name: None)
        monkeypatch.setattr(cli, "_FZF_FALLBACKS", ("/definitely/not/here",))
        assert cli.find_fzf() is None


class TestMissingFzfIsReported:
    @pytest.fixture
    def no_fzf(self, monkeypatch):
        monkeypatch.setattr(cli, "find_fzf", lambda: None)
        monkeypatch.setattr(
            cli,
            "collect_links",
            lambda cwd, active=False: [cli.Link(url="https://a.example", label="A")],
        )

    def test_exits_non_zero(self, no_fzf):
        assert cli.main([]) == 2

    def test_explains_the_problem(self, no_fzf, capsys):
        cli.main([])
        assert "fzf" in capsys.readouterr().err

    def test_still_lists_the_links(self, no_fzf, capsys):
        """Even without a picker, show what was found."""
        cli.main([])
        assert "https://a.example" in capsys.readouterr().out

    def test_print_mode_does_not_need_fzf(self, no_fzf, capsys):
        assert cli.main(["--print"]) == 0
