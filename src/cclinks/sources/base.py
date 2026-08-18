"""What a transcript source has to provide."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

__all__ = ["SessionInfo", "Source"]


@dataclass(frozen=True)
class SessionInfo:
    """Who a link came from.

    Once links are gathered across sessions, a row is only useful if it can say
    which session it belongs to. Every field but the id is best-effort: a
    transcript is not a contract, and a missing title must never cost a row its
    identity.
    """

    session_id: str
    project: str
    cwd: str | None = None
    title: str | None = None
    git_branch: str | None = None
    mtime: float = 0.0

    @property
    def label(self) -> str:
        """The session in one phrase: the project, then what it is about."""
        return f"{self.project}/{self.title or self.session_id.split('-')[0]}"


@dataclass(frozen=True)
class Source:
    name: str
    # cwd=None means "whichever session was updated last".
    find_transcript: Callable[[str | None], Path | None]
    # Message texts, newest first.
    message_texts: Callable[[Path], Iterable[str]]
    # The session the user last typed into, when the source can tell. None when
    # it cannot, or when nothing has been recorded yet.
    active_transcript: Optional[Callable[[], Path | None]] = None
    # Every transcript in scope, newest first. A source that cannot enumerate
    # leaves this out, and only ever offers the one transcript it can find.
    list_transcripts: Optional[Callable[[str | None, str], list[Path]]] = None
    # What to call a transcript's session. Without it, the file name has to do.
    session_info: Optional[Callable[[Path], SessionInfo]] = None
