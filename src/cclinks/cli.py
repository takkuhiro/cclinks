"""Pick a link with fzf and open it.

Nothing is written to the Claude Code terminal: the picker runs elsewhere,
takes a choice, and exits.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import unicodedata

from .collect import SourcedLink, sourced_links
from .links import Link

__all__ = [
    "main",
    "format_line",
    "format_row",
    "format_rows",
    "picker_lines",
    "index_from_line",
    "parse_duration",
    "collect_links",
    "choose",
    "open_url",
    "find_fzf",
]

_SEPARATOR = "  ⟶  "
_ORIGIN_SEPARATOR = "  │  "
# fzf gets the row number in a first field it is told to hide, so the choice is
# resolved by index instead of by parsing the line back apart.
_INDEX_SEPARATOR = "\t"

_RESET = "\x1b[0m"
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
# Cyan label, dim grey URL: the label leads, the URL confirms. The origin is
# context rather than content, so it stays quieter than both.
_DEFAULT_LABEL_COLOR = "36"
_DEFAULT_URL_COLOR = "90"
_DEFAULT_ORIGIN_COLOR = "35"

# Wide enough to tell two sessions apart, narrow enough to leave the label room.
_ORIGIN_MAX = 32

# Reading every session on the machine is the exception, not the default: recent
# sessions are what a picker is for, and the rest are one flag away.
DEFAULT_LIMIT = 20
DEFAULT_SINCE = "7d"

_UNITS = {"m": 60, "h": 3600, "d": 86400, "w": 7 * 86400}
_NO_LIMIT = {"all", "any", "none", "0"}

# A launcher does not inherit an interactive PATH, so look in the usual places too.
_FZF_FALLBACKS = (
    "/opt/homebrew/bin/fzf",
    "/usr/local/bin/fzf",
    "/usr/bin/fzf",
)


def find_fzf() -> str | None:
    found = shutil.which("fzf")
    if found:
        return found
    for candidate in _FZF_FALLBACKS:
        if os.access(candidate, os.X_OK):
            return candidate
    return None


def parse_duration(text: str) -> float | None:
    """Seconds from "30m", "12h", "7d", "2w", or a bare number of days.

    None means no window at all, which is what "all" asks for.
    """
    text = text.strip().lower()
    if text in _NO_LIMIT:
        return None
    unit = _UNITS.get(text[-1:])
    number = text[:-1] if unit else text
    try:
        value = float(number)
    except ValueError:
        raise ValueError(f"not a duration: {text}") from None
    if value < 0:
        raise ValueError(f"not a duration: {text}")
    return value * (unit or _UNITS["d"])


def _sgr(code: str) -> str:
    return f"\x1b[{code}m"


def _char_width(char: str) -> int:
    return 2 if unicodedata.east_asian_width(char) in "WF" else 1


def _display_width(text: str) -> int:
    """Columns a string takes in a terminal.

    Japanese titles are the reason: len() counts a full-width character once and
    the column would be laid out too narrow to line up.
    """
    return sum(_char_width(char) for char in text)


def _fit(text: str, width: int) -> str:
    """Truncate to `width` columns, then pad back out to it."""
    if _display_width(text) > width:
        kept = ""
        remaining = width - 1  # room for the ellipsis
        for char in text:
            remaining -= _char_width(char)
            if remaining < 0:
                break
            kept += char
        text = kept + "…"
    return text + " " * (width - _display_width(text))


def format_line(link: Link, color: bool = False) -> str:
    """One row for fzf: searchable by label, with the URL still visible.

    With `color`, the label and the URL are given different SGR colors so the
    list can be scanned by label alone. Override with CCLINKS_LABEL_COLOR and
    CCLINKS_URL_COLOR, which take raw SGR parameters such as "35" or "1;36".
    """
    if not color:
        return link.url if link.label == link.url else f"{link.label}{_SEPARATOR}{link.url}"

    url_color = _sgr(os.environ.get("CCLINKS_URL_COLOR", _DEFAULT_URL_COLOR))
    if link.label == link.url:
        return f"{url_color}{link.url}{_RESET}"

    label_color = _sgr(os.environ.get("CCLINKS_LABEL_COLOR", _DEFAULT_LABEL_COLOR))
    return (
        f"{label_color}{link.label}{_RESET}"
        f"{_SEPARATOR}"
        f"{url_color}{link.url}{_RESET}"
    )


def format_row(item: SourcedLink, color: bool = False, origin_width: int = 0) -> str:
    """A link, optionally led by the session it came from.

    `origin_width` of zero leaves the origin off entirely, which is what a list
    drawn from a single session wants: naming it on every row says nothing.
    Override the colour with CCLINKS_ORIGIN_COLOR.
    """
    line = format_line(item.link, color=color)
    if origin_width <= 0:
        return line
    origin = _fit(item.session.label, origin_width)
    if color:
        origin_color = _sgr(os.environ.get("CCLINKS_ORIGIN_COLOR", _DEFAULT_ORIGIN_COLOR))
        origin = f"{origin_color}{origin}{_RESET}"
    return f"{origin}{_ORIGIN_SEPARATOR}{line}"


def _origin_max() -> int:
    """The cap on the origin column. CCLINKS_ORIGIN_WIDTH moves it.

    Japanese titles pay double for the cap, so a wide terminal may well want
    more than the default; nonsense in the variable is ignored rather than
    turning the picker into an error.
    """
    try:
        wanted = int(os.environ["CCLINKS_ORIGIN_WIDTH"])
    except (KeyError, ValueError):
        return _ORIGIN_MAX
    return wanted if wanted > 0 else _ORIGIN_MAX


def origin_width(items) -> int:
    """How wide the origin column has to be for these rows."""
    widths = [_display_width(item.session.label) for item in items]
    return min(max(widths, default=0), _origin_max())


def spans_sessions(items) -> bool:
    """Whether these links come from more than one session.

    The one thing that decides whether the origin is worth a column: naming the
    same session on every row says nothing.
    """
    return len({item.session.session_id for item in items}) > 1


def format_rows(items, color: bool = False) -> list[str]:
    """Every link as a row, with the origin column iff it distinguishes anything."""
    width = origin_width(items) if spans_sessions(items) else 0
    return [format_row(item, color=color, origin_width=width) for item in items]


def picker_lines(items, color: bool = False) -> list[str]:
    return [
        f"{position}{_INDEX_SEPARATOR}{row}"
        for position, row in enumerate(format_rows(items, color=color))
    ]


def index_from_line(line: str) -> int | None:
    """The row number fzf handed back, or None if the line is not one of ours."""
    field, separator, _ = line.partition(_INDEX_SEPARATOR)
    if not separator or not field.isdigit():
        return None
    return int(field)


def collect_links(
    cwd: str | None,
    *,
    scope: str = "all",
    limit: int = 0,
    since: float | None = None,
    active: bool = False,
) -> list[SourcedLink]:
    """Links from the sessions in scope, each knowing which session it came from."""
    return sourced_links(cwd, scope=scope, limit=limit, since=since, active=active)


def choose(lines: list[str], header: str | None = None) -> str | None:
    """Let fzf pick a row. None when nothing was chosen.

    `header` puts a line above the list. It is how an empty list says why it is
    empty, and how a list spanning sessions says how far back it reaches.
    """
    argv = [
        find_fzf() or "fzf",
        "--ansi",
        "--prompt=link> ",
        # No --height: a popup or a dedicated tab is already sized for the
        # picker, and asking for a fraction of it left the rest of the window
        # blank -- space the URLs could have used. Run inline in a shell, fzf
        # takes the screen and hands it back on exit.
        "--reverse",
        "--no-multi",
        f"--delimiter={_INDEX_SEPARATOR}",
        # Hide the bookkeeping field from the list and from the search.
        "--with-nth=2..",
    ]
    if header:
        argv += ["--header", header]
    try:
        completed = subprocess.run(
            argv,
            input="\n".join(lines),
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def open_url(url: str) -> bool:
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    try:
        return subprocess.run([opener, url], capture_output=True).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


_WHERE = {
    "session": "this session",
    "project": "this project",
    "all": "every project",
}

_NOWHERE = {
    "session": "in this session",
    "project": "in this project",
    "all": "in any project",
}


def _window(limit: int, since: str | None) -> str | None:
    """How far back the list reaches, or None when it reaches everywhere."""
    parts = []
    if since is not None:
        parts.append(f"last {since}")
    if limit > 0:
        parts.append(f"{limit} sessions")
    return ", ".join(parts) if parts else None


def _header(items, scope: str, limit: int, since: str | None) -> str:
    """What the list covers, above a list that spans more than one session.

    The counts are of what is actually shown. The cap is mentioned only once it
    has bitten, where it stops being trivia and starts being the reason
    something is missing.
    """
    sessions = len({item.session.session_id for item in items})
    parts = [_WHERE[scope]]
    if since is not None:
        parts.append(f"last {since}")
    parts += [f"{sessions} sessions", f"{len(items)} links"]
    if 0 < limit <= sessions:
        parts.append("more with --all")
    return " · ".join(parts)


def _empty_message(scope: str, limit: int, since: str | None) -> str:
    message = f"No links found {_NOWHERE[scope]}"
    window = _window(limit, since)
    if window is None:
        return message
    return f"{message} ({window}) — widen with --all"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cclinks",
        description="Open links from your Claude Code sessions",
    )
    parser.add_argument("--print", action="store_true", help="list links without opening one")
    parser.add_argument("--cwd", default=os.getcwd(), help="target the sessions for this directory")
    parser.add_argument(
        "--scope",
        choices=("session", "project", "all"),
        default="all",
        help="how far to look: one session, one project, or every project (default: all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"how many sessions to read, newest first, 0 for no cap (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--since",
        default=DEFAULT_SINCE,
        metavar="AGE",
        help=f"only sessions touched within, e.g. 12h, 7d, 2w, or all (default: {DEFAULT_SINCE})",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="every session ever recorded: shorthand for --scope all --limit 0 --since all",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="one session only: the most recently updated one, whatever the directory",
    )
    parser.add_argument(
        "--active",
        action="store_true",
        help="one session only: the one you last typed into (requires the UserPromptSubmit hook)",
    )
    parser.add_argument(
        "--no-color", action="store_true", help="do not color the picker"
    )
    args = parser.parse_args(argv)

    try:
        since = parse_duration(args.since)
    except ValueError as error:
        parser.error(str(error))
    since_text = None if since is None else args.since
    limit = max(args.limit, 0)
    scope = args.scope

    if args.all:
        scope, limit, since, since_text = "all", 0, None, None
    if args.latest or args.active:
        # One named session; a window over it could only take it away.
        scope, limit, since, since_text = "session", 0, None, None

    # --active carries its own working directory in the record, and a hotkey's
    # cwd is arbitrary, so neither mode should consult the process's own.
    items = collect_links(
        None if (args.latest or args.active) else args.cwd,
        scope=scope,
        limit=limit,
        since=since,
        active=args.active,
    )

    if args.print:
        if not items:
            # Scripts read this mode, where "nothing found" is worth signalling.
            print(_empty_message(scope, limit, since_text), file=sys.stderr)
            return 1
        # Plain, so the output stays usable in a pipe.
        print("\n".join(format_rows(items)))
        return 0

    if find_fzf() is None:
        # Exiting quietly here would look like the picker simply flashed and vanished.
        if items:
            print("\n".join(format_rows(items)))
        print(
            "fzf not found. Install it (brew install fzf) or check your PATH.",
            file=sys.stderr,
        )
        return 2

    if not items:
        # An empty session is an outcome, not a failure. Exiting non-zero made
        # VS Code call the run a launch failure and leave the tab open with no
        # process to interrupt. Show the picker empty and let Esc close it.
        choose([], header=_empty_message(scope, limit, since_text))
        return 0

    selected = choose(
        picker_lines(items, color=not args.no_color),
        header=_header(items, scope, limit, since_text) if spans_sessions(items) else None,
    )
    if selected is None:
        return 0

    position = index_from_line(selected)
    if position is None or not 0 <= position < len(items):
        return 0
    open_url(items[position].link.url)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
