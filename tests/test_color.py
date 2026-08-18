"""Coloring tests.

The label is what you read; the URL is there for confirmation. Coloring them
differently makes the list scannable. fzf shows them via --ansi, and hands the
original line back on selection, so the URL must survive being parsed out again.
"""

import pytest

from cclinks import cli
from cclinks.collect import SourcedLink
from cclinks.links import Link
from cclinks.sources.base import SessionInfo

LABELLED = Link(url="https://a.example/x", label="Deno のマニュアル")
BARE = Link(url="https://b.example/y", label="https://b.example/y")


class TestPlainFormatting:
    def test_no_escape_codes_by_default(self):
        assert "\x1b[" not in cli.format_line(LABELLED)

    def test_print_mode_stays_plain(self, monkeypatch, capsys):
        item = SourcedLink(link=LABELLED, session=SessionInfo(session_id="s1", project="p"))
        monkeypatch.setattr(cli, "collect_links", lambda cwd, **kwargs: [item])
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


class TestOriginColor:
    """The origin is context, not the thing being read: it must not shout."""

    def item(self):
        return SourcedLink(
            link=LABELLED,
            session=SessionInfo(session_id="s1", project="cclinks", title="出自表示"),
        )

    def test_origin_is_colored_apart_from_the_label(self):
        row = cli.format_row(self.item(), color=True, origin_width=20)
        origin_code = row.split("cclinks")[0].split("\x1b[")[-1]
        label_code = row.split("Deno")[0].split("\x1b[")[-1]
        assert origin_code != label_code

    def test_origin_color_comes_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("CCLINKS_ORIGIN_COLOR", "33")
        assert "\x1b[33m" in cli.format_row(self.item(), color=True, origin_width=20)


class TestRowRecovery:
    """Coloring must not disturb finding the chosen row again."""

    @pytest.mark.parametrize("color", [False, True])
    def test_index_survives_coloring(self, color):
        items = [
            SourcedLink(link=LABELLED, session=SessionInfo(session_id="s1", project="a")),
            SourcedLink(link=BARE, session=SessionInfo(session_id="s2", project="b")),
        ]
        lines = cli.picker_lines(items, color=color)
        assert [cli.index_from_line(line) for line in lines] == [0, 1]
