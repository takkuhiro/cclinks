"""Claude Code transcripts (`~/.claude/projects/**/*.jsonl`)."""

from __future__ import annotations

import json
from pathlib import Path

from .base import Source

__all__ = [
    "message_texts",
    "transcript_for_cwd",
    "latest_transcript",
    "find_transcript",
    "SOURCE",
]

_DEFAULT_PROJECTS = Path.home() / ".claude" / "projects"


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


def find_transcript(cwd: str | None) -> Path | None:
    if cwd is None:
        return latest_transcript()
    return transcript_for_cwd(cwd, fallback=True)


SOURCE = Source(
    name="claude-code",
    find_transcript=find_transcript,
    message_texts=message_texts,
)
