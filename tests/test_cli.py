"""CLI tests.

Covers the rows handed to fzf and the URL recovered from the chosen row.
fzf itself and the browser launch are substituted from outside.
"""

import pytest

from cclinks import cli
from cclinks.links import Link

LINKS = [
    # A Japanese label, to keep multi-byte handling covered.
    Link(url="https://a.example/x", label="記事A"),
    Link(url="https://b.example/y", label="https://b.example/y"),
]


class TestFormat:
    def test_line_contains_label_and_url(self):
        line = cli.format_line(LINKS[0])
        assert "記事A" in line
        assert "https://a.example/x" in line

    def test_bare_url_is_not_duplicated(self):
        assert cli.format_line(LINKS[1]).count("https://b.example/y") == 1

    def test_url_is_recoverable_from_line(self):
        for link in LINKS:
            assert cli.url_from_line(cli.format_line(link)) == link.url

    def test_unparsable_line_returns_none(self):
        assert cli.url_from_line("just some text") is None

    def test_empty_line_returns_none(self):
        assert cli.url_from_line("") is None


class TestMain:
    @pytest.fixture(autouse=True)
    def fzf_present(self, monkeypatch):
        """Pretend fzf is installed.

        Without this the picker path is never reached on a machine that has no
        fzf, and these tests would pass locally while failing in CI.
        """
        monkeypatch.setattr(cli, "find_fzf", lambda: "/usr/bin/fzf")

    @pytest.fixture
    def opened(self, monkeypatch):
        calls = []
        monkeypatch.setattr(cli, "open_url", lambda url: calls.append(url) or True)
        return calls

    def test_opens_the_selected_url(self, monkeypatch, opened):
        monkeypatch.setattr(cli, "collect_links", lambda cwd, active=False: LINKS)
        monkeypatch.setattr(cli, "choose", lambda lines: cli.format_line(LINKS[1]))
        assert cli.main([]) == 0
        assert opened == ["https://b.example/y"]

    def test_does_nothing_when_selection_cancelled(self, monkeypatch, opened):
        monkeypatch.setattr(cli, "collect_links", lambda cwd, active=False: LINKS)
        monkeypatch.setattr(cli, "choose", lambda lines: None)
        assert cli.main([]) == 0
        assert opened == []

    def test_latest_ignores_cwd(self, monkeypatch, opened):
        """--latest must not consult the working directory.

        A launcher's working directory can happen to match another project's
        session directory, which would silently select the wrong transcript.
        """
        seen = {}
        monkeypatch.setattr(
            cli,
            "collect_links",
            lambda cwd, active=False: seen.setdefault("cwd", cwd) and [] or LINKS,
        )
        monkeypatch.setattr(cli, "choose", lambda lines: None)
        cli.main(["--latest"])
        assert seen["cwd"] is None

    def test_print_only_mode_lists_without_opening(self, monkeypatch, opened, capsys):
        monkeypatch.setattr(cli, "collect_links", lambda cwd, active=False: LINKS)
        assert cli.main(["--print"]) == 0
        out = capsys.readouterr().out
        assert "https://a.example/x" in out
        assert opened == []


class TestEmptySession:
    """A session with no links is a normal outcome, not a failure.

    Exiting non-zero made VS Code report the run as "failed to launch" and left
    the task tab open with no process behind it, so Ctrl-C could not close it.
    The picker opens on an empty list instead, and the message rides along as a
    header: it stays readable, and Esc closes it the same way a real pick does.
    """

    @pytest.fixture(autouse=True)
    def fzf_present(self, monkeypatch):
        monkeypatch.setattr(cli, "find_fzf", lambda: "/usr/bin/fzf")

    @pytest.fixture(autouse=True)
    def no_links(self, monkeypatch):
        monkeypatch.setattr(cli, "collect_links", lambda cwd, active=False: [])

    @pytest.fixture
    def picker(self, monkeypatch):
        seen = {}

        def fake_choose(lines, header=None):
            seen["lines"] = lines
            seen["header"] = header
            return None

        monkeypatch.setattr(cli, "choose", fake_choose)
        return seen

    def test_exits_zero(self, picker):
        assert cli.main([]) == 0

    def test_message_reaches_the_picker(self, picker):
        cli.main([])
        assert picker["lines"] == []
        assert "No links" in picker["header"]

    def test_print_mode_still_exits_non_zero(self, capsys):
        """--print is read by scripts, where "nothing found" is worth signalling."""
        assert cli.main(["--print"]) == 1
        assert "No links" in capsys.readouterr().err


class TestChoose:
    """The header is how the empty case explains itself, so fzf must receive it."""

    @pytest.fixture
    def fzf_argv(self, monkeypatch):
        monkeypatch.setattr(cli, "find_fzf", lambda: "/usr/bin/fzf")
        recorded = {}

        class Cancelled:
            returncode = 130
            stdout = ""

        def fake_run(argv, **kwargs):
            recorded["argv"] = argv
            return Cancelled()

        monkeypatch.setattr(cli.subprocess, "run", fake_run)
        return recorded

    def test_header_is_handed_to_fzf(self, fzf_argv):
        cli.choose([], header="No links found in this session")
        assert "--header" in fzf_argv["argv"]
        assert "No links found in this session" in fzf_argv["argv"]

    def test_no_header_when_there_are_links(self, fzf_argv):
        cli.choose(["https://a.example"])
        assert "--header" not in fzf_argv["argv"]
