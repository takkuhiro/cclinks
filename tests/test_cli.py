"""CLI tests.

Covers the rows handed to fzf, the origin column that says which session a row
came from, and the row recovered from what fzf hands back.  fzf itself and the
browser launch are substituted from outside.
"""

import pytest

from cclinks import cli
from cclinks.collect import SourcedLink
from cclinks.links import Link
from cclinks.sources.base import SessionInfo

LINKS = [
    # A Japanese label, to keep multi-byte handling covered.
    Link(url="https://a.example/x", label="記事A"),
    Link(url="https://b.example/y", label="https://b.example/y"),
]

SESSION = SessionInfo(session_id="a98d5202-6e0e", project="cclinks", title="出自表示")
OTHER = SessionInfo(session_id="b1234567-0000", project="techblogs", title="記事の下書き")


def sourced(links=LINKS, session=SESSION):
    return [SourcedLink(link=link, session=session) for link in links]


ITEMS = sourced()
MIXED = sourced([LINKS[0]], SESSION) + sourced([LINKS[1]], OTHER)


class TestFormat:
    def test_line_contains_label_and_url(self):
        line = cli.format_line(LINKS[0])
        assert "記事A" in line
        assert "https://a.example/x" in line

    def test_bare_url_is_not_duplicated(self):
        assert cli.format_line(LINKS[1]).count("https://b.example/y") == 1

    def test_no_origin_column_by_default(self):
        assert cli.format_row(ITEMS[0]) == cli.format_line(LINKS[0])

    def test_origin_column_names_the_session(self):
        row = cli.format_row(ITEMS[0], origin_width=20)
        assert "cclinks/出自表示" in row
        assert row.index("cclinks") < row.index("記事A")

    def test_origin_column_is_padded_to_a_common_width(self):
        rows = [cli.format_row(item, origin_width=24) for item in MIXED]
        assert len({row.index(cli._SEPARATOR) for row in rows}) == 1

    def test_a_long_origin_is_truncated_to_the_column(self):
        wordy = SessionInfo(session_id="c1", project="p", title="と" * 40)
        row = cli.format_row(SourcedLink(link=LINKS[0], session=wordy), origin_width=12)
        assert "…" in row
        assert cli._display_width(row.split(cli._ORIGIN_SEPARATOR)[0]) == 12

    def test_color_leaves_the_text_intact(self):
        plain = cli.format_row(ITEMS[0], origin_width=20)
        colored = cli.format_row(ITEMS[0], color=True, origin_width=20)
        assert cli._ANSI.sub("", colored) == plain


class TestDisplayWidth:
    """Padding a column of Japanese titles needs the printed width, not len()."""

    def test_wide_characters_count_double(self):
        assert cli._display_width("記事") == 4

    def test_ascii_counts_once(self):
        assert cli._display_width("abc") == 3


class TestPickerLines:
    """fzf hands the chosen line back verbatim; the row is found by index, not by parsing."""

    def test_a_row_is_recoverable_from_the_chosen_line(self):
        lines = cli.picker_lines(MIXED, show_origin=True)
        for position, line in enumerate(lines):
            assert cli.index_from_line(line) == position

    def test_origin_is_omitted_when_asked(self):
        line = cli.picker_lines(ITEMS, show_origin=False)[0]
        assert "cclinks" not in line

    def test_unparsable_line_returns_none(self):
        assert cli.index_from_line("just some text") is None

    def test_empty_line_returns_none(self):
        assert cli.index_from_line("") is None


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

    @pytest.fixture
    def collector(self, monkeypatch):
        """Record how main asked for links, and hand back MIXED."""
        seen = {}

        def fake_collect(cwd, **kwargs):
            seen["cwd"] = cwd
            seen.update(kwargs)
            return MIXED

        monkeypatch.setattr(cli, "collect_links", fake_collect)
        return seen

    def test_opens_the_selected_url(self, monkeypatch, collector, opened):
        monkeypatch.setattr(cli, "choose", lambda lines, header=None: lines[1])
        assert cli.main([]) == 0
        assert opened == [LINKS[1].url]

    def test_does_nothing_when_selection_cancelled(self, monkeypatch, collector, opened):
        monkeypatch.setattr(cli, "choose", lambda lines, header=None: None)
        assert cli.main([]) == 0
        assert opened == []

    def test_gathers_every_session_by_default(self, monkeypatch, collector, opened):
        """The default answers "what have I seen lately", not "what is in this tab"."""
        monkeypatch.setattr(cli, "choose", lambda lines, header=None: None)
        cli.main([])
        assert collector["scope"] == "all"
        assert collector["limit"] == cli.DEFAULT_LIMIT
        assert collector["since"] == cli.parse_duration(cli.DEFAULT_SINCE)

    def test_all_flag_removes_both_limits(self, monkeypatch, collector, opened):
        monkeypatch.setattr(cli, "choose", lambda lines, header=None: None)
        cli.main(["--all"])
        assert collector["scope"] == "all"
        assert collector["limit"] == 0
        assert collector["since"] is None

    def test_scope_project_keeps_to_this_directory(self, monkeypatch, collector, opened):
        monkeypatch.setattr(cli, "choose", lambda lines, header=None: None)
        cli.main(["--scope", "project", "--cwd", "/here"])
        assert (collector["scope"], collector["cwd"]) == ("project", "/here")

    def test_limit_and_since_are_passed_through(self, monkeypatch, collector, opened):
        monkeypatch.setattr(cli, "choose", lambda lines, header=None: None)
        cli.main(["--limit", "3", "--since", "12h"])
        assert collector["limit"] == 3
        assert collector["since"] == 12 * 3600

    def test_latest_ignores_cwd(self, monkeypatch, collector, opened):
        """--latest must not consult the working directory.

        A launcher's working directory can happen to match another project's
        session directory, which would silently select the wrong transcript.
        """
        monkeypatch.setattr(cli, "choose", lambda lines, header=None: None)
        cli.main(["--latest"])
        assert collector["cwd"] is None
        assert collector["scope"] == "session"

    def test_print_only_mode_lists_without_opening(self, monkeypatch, collector, opened, capsys):
        assert cli.main(["--print"]) == 0
        out = capsys.readouterr().out
        assert "https://a.example/x" in out
        assert opened == []

    def test_print_names_the_session_when_there_is_more_than_one(self, collector, capsys):
        assert cli.main(["--print"]) == 0
        assert "techblogs" in capsys.readouterr().out


class TestOriginColumnAppears:
    """The origin only earns its space when there is more than one session."""

    @pytest.fixture(autouse=True)
    def fzf_present(self, monkeypatch):
        monkeypatch.setattr(cli, "find_fzf", lambda: "/usr/bin/fzf")

    @pytest.fixture
    def picker(self, monkeypatch):
        seen = {}

        def fake_choose(lines, header=None):
            seen["lines"] = lines
            seen["header"] = header
            return None

        monkeypatch.setattr(cli, "choose", fake_choose)
        return seen

    def collecting(self, monkeypatch, items):
        monkeypatch.setattr(cli, "collect_links", lambda cwd, **kwargs: items)

    def test_shown_across_sessions(self, monkeypatch, picker):
        self.collecting(monkeypatch, MIXED)
        cli.main([])
        assert all("cclinks" in line or "techblogs" in line for line in picker["lines"])

    def test_hidden_within_one_session(self, monkeypatch, picker):
        self.collecting(monkeypatch, ITEMS)
        cli.main([])
        assert not any("cclinks/" in line for line in picker["lines"])

    def test_header_counts_the_sessions(self, monkeypatch, picker):
        self.collecting(monkeypatch, MIXED)
        cli.main([])
        assert "2 sessions" in picker["header"]

    def test_no_header_within_one_session(self, monkeypatch, picker):
        self.collecting(monkeypatch, ITEMS)
        cli.main([])
        assert picker["header"] is None


class TestDuration:
    def test_accepts_the_usual_units(self):
        assert cli.parse_duration("30m") == 1800
        assert cli.parse_duration("12h") == 12 * 3600
        assert cli.parse_duration("7d") == 7 * 86400
        assert cli.parse_duration("2w") == 14 * 86400

    def test_a_bare_number_is_days(self):
        assert cli.parse_duration("3") == 3 * 86400

    def test_all_means_no_limit(self):
        assert cli.parse_duration("all") is None

    def test_rejects_nonsense(self):
        with pytest.raises(ValueError):
            cli.parse_duration("soon")


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
        monkeypatch.setattr(cli, "collect_links", lambda cwd, **kwargs: [])

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

    def test_says_how_to_look_further_back(self, picker):
        """Empty under a 7-day window is not the same as empty everywhere."""
        cli.main([])
        assert "--all" in picker["header"]

    def test_no_such_hint_once_nothing_is_filtered(self, picker):
        cli.main(["--all"])
        assert "--all" not in picker["header"]

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
        cli.choose(["0\thttps://a.example"])
        assert "--header" not in fzf_argv["argv"]

    def test_the_index_field_is_hidden(self, fzf_argv):
        """The index is bookkeeping: it must not be shown, nor searched."""
        cli.choose(["0\thttps://a.example"])
        assert "--with-nth=2.." in fzf_argv["argv"]
        assert "--delimiter=\t" in fzf_argv["argv"]
