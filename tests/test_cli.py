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
    @pytest.fixture
    def opened(self, monkeypatch):
        calls = []
        monkeypatch.setattr(cli, "open_url", lambda url: calls.append(url) or True)
        return calls

    def test_opens_the_selected_url(self, monkeypatch, opened):
        monkeypatch.setattr(cli, "collect_links", lambda cwd: LINKS)
        monkeypatch.setattr(cli, "choose", lambda lines: cli.format_line(LINKS[1]))
        assert cli.main([]) == 0
        assert opened == ["https://b.example/y"]

    def test_does_nothing_when_selection_cancelled(self, monkeypatch, opened):
        monkeypatch.setattr(cli, "collect_links", lambda cwd: LINKS)
        monkeypatch.setattr(cli, "choose", lambda lines: None)
        assert cli.main([]) == 0
        assert opened == []

    def test_reports_when_no_links(self, monkeypatch, opened, capsys):
        monkeypatch.setattr(cli, "collect_links", lambda cwd: [])
        assert cli.main([]) == 1
        assert "No links" in capsys.readouterr().err
        assert opened == []

    def test_latest_ignores_cwd(self, monkeypatch, opened):
        """--latest must not consult the working directory.

        A launcher's working directory can happen to match another project's
        session directory, which would silently select the wrong transcript.
        """
        seen = {}
        monkeypatch.setattr(
            cli, "collect_links", lambda cwd: seen.setdefault("cwd", cwd) and [] or LINKS
        )
        monkeypatch.setattr(cli, "choose", lambda lines: None)
        cli.main(["--latest"])
        assert seen["cwd"] is None

    def test_print_only_mode_lists_without_opening(self, monkeypatch, opened, capsys):
        monkeypatch.setattr(cli, "collect_links", lambda cwd: LINKS)
        assert cli.main(["--print"]) == 0
        out = capsys.readouterr().out
        assert "https://a.example/x" in out
        assert opened == []
