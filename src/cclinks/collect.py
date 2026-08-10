"""Turn a session into a list of links.

This is the part every source shares: given message texts newest first, produce
the links in the order they should be offered.
"""

from __future__ import annotations

from .links import Link, extract_links, merge_links
from .sources import Source, get

__all__ = ["links_from_texts", "links_for_session"]


def links_from_texts(texts) -> list[Link]:
    """Links from message texts, which must already be newest first."""
    result: list[Link] = []
    for text in texts:
        merge_links(result, extract_links(text))
    return result


def links_for_session(
    cwd: str | None, source: Source | None = None, active: bool = False
) -> list[Link]:
    """Links from the session for `cwd`, or from the newest one when cwd is None.

    With `active`, prefer the session the user last typed into. That record only
    exists once the hook is installed, so an unrecorded session falls through to
    the usual lookup rather than coming back empty.
    """
    source = source or get()
    transcript = None
    if active and source.active_transcript is not None:
        transcript = source.active_transcript()
    if transcript is None:
        transcript = source.find_transcript(cwd)
    if transcript is None:
        return []
    return links_from_texts(source.message_texts(transcript))
