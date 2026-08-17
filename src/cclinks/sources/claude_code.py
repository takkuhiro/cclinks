"""Claude Code transcripts (`~/.claude/projects/**/*.jsonl`)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .base import SessionInfo, Source

__all__ = [
    "message_texts",
    "session_info",
    "transcript_for_cwd",
    "transcripts_for_cwd",
    "latest_transcript",
    "all_transcripts",
    "list_transcripts",
    "active_transcript",
    "find_transcript",
    "SOURCE",
]

_DEFAULT_PROJECTS = Path.home() / ".claude" / "projects"
_DEFAULT_ACTIVE_FILE = Path.home() / ".claude" / "cclinks-active.json"

# A session names itself in one line; anything longer is a paragraph, not a name.
_TITLE_MAX = 60


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


def _rows(path: Path):
    """Parsed JSONL rows, newest first. A file that will not read yields nothing."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            yield row


def message_texts(path: str | Path) -> list[str]:
    """Message texts from a transcript, newest first."""
    texts: list[str] = []
    for row in _rows(Path(path)):
        if row.get("type") not in ("assistant", "user"):
            continue
        # Subagent turns never reach the screen, so they are not what the user saw.
        if row.get("isSidechain"):
            continue
        text = _text_of(row.get("message", {}))
        if text:
            texts.append(text)
    return texts


def _shorten(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= _TITLE_MAX else text[: _TITLE_MAX - 1] + "…"


def _project_of(path: Path, cwd: str | None) -> str:
    """A short name for the project a session belongs to.

    The working directory recorded in the transcript is the reliable source.
    Falling back to the encoded directory name is guesswork -- slashes and
    dashes are both written as dashes -- but a wrong-looking last segment still
    beats showing nothing.
    """
    if cwd:
        return Path(cwd).name or cwd
    encoded = path.parent.name.strip("-")
    return encoded.rsplit("-", 1)[-1] or path.parent.name


def session_info(path: str | Path) -> SessionInfo:
    """Name the session a transcript belongs to.

    Read from the end: the title a session settled on, the directory it ran in
    and the branch it was on are all near the tail, so this stops as soon as it
    has both. None of these rows are guaranteed to exist, which is why every one
    of them has something behind it.
    """
    path = Path(path)
    title = None
    last_prompt = None
    cwd = None
    branch = None

    for row in _rows(path):
        kind = row.get("type")
        if kind == "ai-title" and title is None:
            candidate = row.get("aiTitle")
            if isinstance(candidate, str) and candidate.strip():
                title = _shorten(candidate)
        elif kind == "last-prompt" and last_prompt is None:
            candidate = row.get("lastPrompt")
            if isinstance(candidate, str) and candidate.strip():
                last_prompt = _shorten(candidate)
        if cwd is None and isinstance(row.get("cwd"), str):
            cwd = row["cwd"]
            branch = row.get("gitBranch") or None
        if title is not None and cwd is not None:
            break

    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0

    return SessionInfo(
        session_id=path.stem,
        project=_project_of(path, cwd),
        cwd=cwd,
        title=title or last_prompt,
        git_branch=branch,
        mtime=mtime,
    )


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:  # vanished between the glob and the stat
        return 0.0


def _by_mtime(paths) -> list[Path]:
    return sorted(paths, key=_mtime, reverse=True)


def _newest(paths) -> Path | None:
    found = _by_mtime(paths)
    return found[0] if found else None


def _projects_root(projects_dir: Path | str | None) -> Path:
    return Path(projects_dir) if projects_dir is not None else _DEFAULT_PROJECTS


def _encoded(cwd: str | Path) -> str:
    # Claude Code names the project directory after the path, slashes turned into dashes.
    return str(Path(cwd)).replace("/", "-").replace("_", "-").replace(".", "-")


def all_transcripts(projects_dir: Path | str | None = None) -> list[Path]:
    """Every session of every project, newest first."""
    root = _projects_root(projects_dir)
    if not root.is_dir():
        return []
    return _by_mtime(root.glob("*/*.jsonl"))


def transcripts_for_cwd(
    cwd: str | Path, projects_dir: Path | str | None = None
) -> list[Path]:
    """Every session of one project, newest first."""
    directory = _projects_root(projects_dir) / _encoded(cwd)
    if not directory.is_dir():
        return []
    return _by_mtime(directory.glob("*.jsonl"))


def list_transcripts(cwd: str | None, scope: str = "all") -> list[Path]:
    """The transcripts a scope covers, newest first."""
    if scope == "project" and cwd is not None:
        return transcripts_for_cwd(cwd)
    return all_transcripts()


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
    directory = _projects_root(projects_dir) / _encoded(cwd)

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
    list_transcripts=list_transcripts,
    session_info=session_info,
)
