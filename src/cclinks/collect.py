"""Turn sessions into a list of links.

This is the part every source shares: given message texts newest first, produce
the links in the order they should be offered. Gathering more than one session
adds one thing to that -- every link remembers which session it came from, so a
list spanning projects and tabs can still say where each row is from.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from .links import Link, extract_links, improves_label, merge_links
from .sources import SessionInfo, Source, get

__all__ = ["SourcedLink", "links_from_texts", "sourced_links"]


@dataclass(frozen=True)
class SourcedLink:
    link: Link
    session: SessionInfo


def links_from_texts(texts) -> list[Link]:
    """Links from message texts, which must already be newest first."""
    result: list[Link] = []
    for text in texts:
        merge_links(result, extract_links(text))
    return result


def _transcripts(source: Source, cwd: str | None, scope: str, active: bool) -> list:
    """The transcripts to read, newest first.

    `active` narrows to the session the user last typed into. That record only
    exists once the hook is installed, so an unrecorded session falls through to
    the usual lookup rather than coming back empty.
    """
    if active and source.active_transcript is not None:
        recorded = source.active_transcript()
        if recorded is not None:
            return [recorded]
    if active or scope == "session" or source.list_transcripts is None:
        found = source.find_transcript(cwd)
        return [found] if found is not None else []
    return list(source.list_transcripts(cwd, scope))


def _session_info(source: Source, path) -> SessionInfo:
    if source.session_info is not None:
        return source.session_info(path)
    # A source that cannot describe its sessions still has a file name to go on.
    name = Path(str(path))
    return SessionInfo(session_id=name.stem, project=name.parent.name)


def sourced_links(
    cwd: str | None,
    source: Source | None = None,
    *,
    scope: str = "all",
    limit: int = 0,
    since: float | None = None,
    active: bool = False,
    now: float | None = None,
) -> list[SourcedLink]:
    """Links from the sessions `scope` covers, newest session first.

    `limit` caps how many sessions are read, and `since` drops the ones that
    have not been touched within that many seconds. Both are applied to sessions
    rather than to links: a cap on links would silently cut a session in half.
    The cap comes first so that a wide scope does not have to open every
    transcript on the machine just to find out how old it is.

    A URL seen in more than one session is listed once, under the newest session
    that mentioned it. A later, older mention still gets to supply a label the
    newer one lacked: pasted output often names a URL bare.
    """
    source = source or get()

    paths = _transcripts(source, cwd, scope, active)
    if limit > 0:
        paths = paths[:limit]

    result: list[SourcedLink] = []
    position_of: dict[str, int] = {}
    cutoff = None if since is None else (time.time() if now is None else now) - since

    for path in paths:
        info = _session_info(source, path)
        if cutoff is not None and info.mtime < cutoff:
            continue
        for link in links_from_texts(source.message_texts(path)):
            position = position_of.get(link.url)
            if position is None:
                position_of[link.url] = len(result)
                result.append(SourcedLink(link=link, session=info))
                continue
            stored = result[position]
            if improves_label(stored.link, link):
                result[position] = SourcedLink(link=link, session=stored.session)
    return result
