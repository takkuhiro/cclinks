"""Claude Code transcripts (`~/.claude/projects/**/*.jsonl`)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .base import Source

__all__ = [
    "message_texts",
    "transcript_for_cwd",
    "latest_transcript",
    "active_transcript",
    "find_transcript",
    "SOURCE",
]

_DEFAULT_PROJECTS = Path.home() / ".claude" / "projects"
_DEFAULT_ACTIVE_FILE = Path.home() / ".claude" / "cclinks-active.json"


def _text_of(message) -> str:
    if isinstance(message, str):
        return message
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def message_texts(path: str | Path) -> list[str]:
    """Message texts from a transcript, newest first."""
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    texts: list[str] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or row.get("type") not in ("assistant", "user"):
            continue
        # Subagent turns never reach the screen, so they are not what the user saw.
        if row.get("isSidechain"):
            continue
        text = _text_of(row.get("message", {}))
        if text:
            texts.append(text)
    return texts


def _newest(paths) -> Path | None:
    found = sorted(paths, key=lambda path: path.stat().st_mtime, reverse=True)
    return found[0] if found else None


def _projects_root(projects_dir: Path | str | None) -> Path:
    return Path(projects_dir) if projects_dir is not None else _DEFAULT_PROJECTS


def latest_transcript(projects_dir: Path | str | None = None) -> Path | None:
    """The most recently updated transcript, whatever the project."""
    root = _projects_root(projects_dir)
    if not root.is_dir():
        return None
    return _newest(root.glob("*/*.jsonl"))


def transcript_for_cwd(
    cwd: str | Path, projects_dir: Path | str | None = None, fallback: bool = False
) -> Path | None:
    """The newest transcript belonging to a working directory.

    With `fallback`, fall back to the most recent session anywhere, which is what
    you want when the working directory is arbitrary.
    """
    root = _projects_root(projects_dir)
    # Claude Code names the project directory after the path, slashes turned into dashes.
    encoded = str(Path(cwd)).replace("/", "-").replace("_", "-").replace(".", "-")
    directory = root / encoded

    if directory.is_dir():
        exact = _newest(directory.glob("*.jsonl"))
        if exact is not None:
            return exact

    return latest_transcript(projects_dir) if fallback else None


def _active_file() -> Path:
    override = os.environ.get("CCLINKS_ACTIVE_FILE")
    return Path(override) if override else _DEFAULT_ACTIVE_FILE


def active_transcript(
    active_file: Path | str | None = None, projects_dir: Path | str | None = None
) -> Path | None:
    """The transcript of the session the user last typed into.

    A picker launched from a hotkey is not a child of Claude Code, so it cannot
    read CLAUDE_CODE_SESSION_ID. The session announces itself through a
    UserPromptSubmit hook instead, which writes the record this reads.

    This exists because mtime is the wrong signal: the newest transcript belongs
    to whichever session wrote last, which may be another tab working through a
    long task while the user watches this one. None when no record is readable,
    leaving the caller to fall back.
    """
    path = Path(active_file) if active_file is not None else _active_file()
    try:
        recorded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(recorded, dict):
        return None

    transcript = recorded.get("transcript_path")
    if transcript and Path(transcript).is_file():
        return Path(transcript)

    # The transcript named in the record is gone; the directory it belonged to
    # is still the best answer available.
    cwd = recorded.get("cwd")
    return transcript_for_cwd(cwd, projects_dir) if cwd else None


def find_transcript(cwd: str | None) -> Path | None:
    if cwd is None:
        return latest_transcript()
    return transcript_for_cwd(cwd, fallback=True)


SOURCE = Source(
    name="claude-code",
    find_transcript=find_transcript,
    message_texts=message_texts,
    active_transcript=active_transcript,
)
