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

from .collect import links_for_session
from .links import Link

__all__ = [
    "main",
    "format_line",
    "url_from_line",
    "collect_links",
    "choose",
    "open_url",
    "find_fzf",
]

_SEPARATOR = "  ⟶  "

_EMPTY_MESSAGE = "No links found in this session"

_RESET = "\x1b[0m"
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
# Cyan label, dim grey URL: the label leads, the URL confirms.
_DEFAULT_LABEL_COLOR = "36"
_DEFAULT_URL_COLOR = "90"

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


def _sgr(code: str) -> str:
    return f"\x1b[{code}m"


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


def url_from_line(line: str) -> str | None:
    if not line:
        return None
    # fzf hands back the line as it was given, escape codes and all.
    candidate = _ANSI.sub("", line).split(_SEPARATOR)[-1].strip()
    return candidate if candidate.startswith(("http://", "https://")) else None


def collect_links(cwd: str | None, active: bool = False) -> list[Link]:
    """Links from the session for `cwd`, or from the newest session when it is None."""
    return links_for_session(cwd, active=active)


def choose(lines: list[str], header: str | None = None) -> str | None:
    """Let fzf pick a row. None when nothing was chosen.

    `header` puts a line above the list. It is how an empty list says why it is
    empty, instead of the picker appearing to have nothing to show.
    """
    argv = [
        find_fzf() or "fzf",
        "--ansi",
        "--prompt=link> ",
        "--height=40%",
        "--reverse",
        "--no-multi",
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cclinks",
        description="Open links from a Claude Code session",
    )
    parser.add_argument("--print", action="store_true", help="list links without opening one")
    parser.add_argument("--cwd", default=os.getcwd(), help="target the session for this directory")
    parser.add_argument(
        "--latest",
        action="store_true",
        help="ignore the working directory and use the most recent session",
    )
    parser.add_argument(
        "--active",
        action="store_true",
        help="use the session you last typed into (requires the UserPromptSubmit hook)",
    )
    parser.add_argument(
        "--no-color", action="store_true", help="do not color the picker"
    )
    args = parser.parse_args(argv)

    # --active carries its own working directory in the record, and a hotkey's
    # cwd is arbitrary, so neither mode should consult the process's own.
    links = collect_links(
        None if (args.latest or args.active) else args.cwd, active=args.active
    )

    if args.print:
        if not links:
            # Scripts read this mode, where "nothing found" is worth signalling.
            print(_EMPTY_MESSAGE, file=sys.stderr)
            return 1
        # Plain, so the output stays usable in a pipe.
        print("\n".join(format_line(link) for link in links))
        return 0

    if find_fzf() is None:
        # Exiting quietly here would look like the picker simply flashed and vanished.
        if links:
            print("\n".join(format_line(link) for link in links))
        print(
            "fzf not found. Install it (brew install fzf) or check your PATH.",
            file=sys.stderr,
        )
        return 2

    if not links:
        # An empty session is an outcome, not a failure. Exiting non-zero made
        # VS Code call the run a launch failure and leave the tab open with no
        # process to interrupt. Show the picker empty and let Esc close it.
        choose([], header=_EMPTY_MESSAGE)
        return 0

    selected = choose([format_line(link, color=not args.no_color) for link in links])
    if selected is None:
        return 0

    url = url_from_line(selected)
    if url is None:
        return 0
    open_url(url)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
