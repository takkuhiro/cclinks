"""What a transcript source has to provide."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

__all__ = ["Source"]


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
