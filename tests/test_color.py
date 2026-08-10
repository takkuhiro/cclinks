"""Coloring tests.

The label is what you read; the URL is there for confirmation. Coloring them
differently makes the list scannable. fzf shows them via --ansi, and hands the
original line back on selection, so the URL must survive being parsed out again.
"""

import pytest

from cclinks import cli
from cclinks.links import Link

LABELLED = Link(url="https://a.example/x", label="Deno のマニュアル")
BARE = Link(url="https://b.example/y", label="https://b.example/y")


class TestPlainFormatting:
    def test_no_escape_codes_by_default(self):
        assert "\x1b[" not in cli.format_line(LABELLED)

    def test_print_mode_stays_plain(self, monkeypatch, capsys):
        monkeypatch.setattr(cli, "collect_links", lambda cwd, active=False: [LABELLED])
        cli.main(["--print"])
        assert "\x1b[" not in capsys.readouterr().out


class TestColoredFormatting:
    def test_label_and_url_get_different_colors(self):
        line = cli.format_line(LABELLED, color=True)
        label_code = line.split("Deno")[0]
        url_code = line.split("https://")[0].split("\x1b[")[-1]
        assert label_code != url_code

    def test_label_text_is_intact(self):
        assert "Deno のマニュアル" in cli.format_line(LABELLED, color=True)

    def test_url_text_is_intact(self):
        assert "https://a.example/x" in cli.format_line(LABELLED, color=True)

    def test_line_is_reset_at_the_end(self):
        assert cli.format_line(LABELLED, color=True).endswith("\x1b[0m")

    def test_bare_url_is_still_shown_once(self):
        line = cli.format_line(BARE, color=True)
        assert line.count("https://b.example/y") == 1

    def test_colors_come_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("CCLINKS_LABEL_COLOR", "35")
        assert "\x1b[35m" in cli.format_line(LABELLED, color=True)

    def test_url_color_comes_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("CCLINKS_URL_COLOR", "32")
        assert "\x1b[32m" in cli.format_line(LABELLED, color=True)


class TestUrlRecovery:
    @pytest.mark.parametrize("link", [LABELLED, BARE])
    def test_url_survives_coloring(self, link):
        assert cli.url_from_line(cli.format_line(link, color=True)) == link.url

    def test_strips_escape_codes_before_matching(self):
        assert cli.url_from_line("\x1b[90mhttps://a.example/x\x1b[0m") == "https://a.example/x"

    def test_still_rejects_non_urls(self):
        assert cli.url_from_line("\x1b[36mjust a label\x1b[0m") is None
