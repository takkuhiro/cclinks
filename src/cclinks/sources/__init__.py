"""Where transcripts come from.

A source knows two things and nothing else: how to find the transcript to read,
and how to pull the message texts out of it. Everything downstream — extracting
links, deduplicating, picking, opening — is shared.

Only Claude Code is implemented. Another agent that keeps a local transcript
(Codex CLI writes ~/.codex/sessions/**/rollout-*.jsonl, for one) would be a new
module here plus an entry in SOURCES.
"""

from __future__ import annotations

from . import claude_code
from .base import Source

__all__ = ["Source", "SOURCES", "DEFAULT_SOURCE", "get"]

SOURCES: dict[str, Source] = {
    "claude": claude_code.SOURCE,
}

DEFAULT_SOURCE = "claude"


def get(name: str = DEFAULT_SOURCE) -> Source:
    return SOURCES[name]
