"""Where a link came from.

A list gathered across sessions is only usable if each row can say which
session it belongs to. Claude Code's transcript already carries enough to
name one: the working directory, the branch, and the title it gave itself.
None of those fields are contractual, so every one of them has a fallback.
"""

import json
import os

from cclinks.sources.base import SessionInfo
from cclinks.sources.claude_code import (
    all_transcripts,
    list_transcripts,
    session_info,
    transcripts_for_cwd,
)


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def user(text, **fields):
    row = {"type": "user", "message": {"role": "user", "content": text}}
    row.update(fields)
    return row


class TestSessionInfo:
    def test_reads_the_title_the_session_gave_itself(self, tmp_path):
        path = write(
            tmp_path / "a98d5202-6e0e-4beb.jsonl",
            [
                user("hi", cwd="/Users/me/develop/cclinks", gitBranch="main"),
                {"type": "ai-title", "aiTitle": "リンク一覧の出自表示"},
            ],
        )
        info = session_info(path)
        assert info.title == "リンク一覧の出自表示"
        assert info.cwd == "/Users/me/develop/cclinks"
        assert info.git_branch == "main"
        assert info.session_id == "a98d5202-6e0e-4beb"

    def test_project_is_the_working_directory_name(self, tmp_path):
        path = write(tmp_path / "s.jsonl", [user("hi", cwd="/Users/me/develop/cclinks")])
        assert session_info(path).project == "cclinks"

    def test_latest_title_wins(self, tmp_path):
        """A session retitles itself as it goes; the last word is the current one."""
        path = write(
            tmp_path / "s.jsonl",
            [
                {"type": "ai-title", "aiTitle": "first guess"},
                user("hi"),
                {"type": "ai-title", "aiTitle": "settled on"},
            ],
        )
        assert session_info(path).title == "settled on"

    def test_falls_back_to_the_last_prompt(self, tmp_path):
        """No title yet: what the user last asked still identifies the session."""
        path = write(
            tmp_path / "s.jsonl",
            [user("hi"), {"type": "last-prompt", "lastPrompt": "fix   the\nflaky test"}],
        )
        assert session_info(path).title == "fix the flaky test"

    def test_long_fallback_titles_are_shortened(self, tmp_path):
        path = write(
            tmp_path / "s.jsonl",
            [{"type": "last-prompt", "lastPrompt": "word " * 40}],
        )
        assert len(session_info(path).title) <= 60

    def test_project_falls_back_to_the_directory_name(self, tmp_path):
        """No row carried a cwd, so the encoded project directory is all there is."""
        path = write(tmp_path / "-Users-me-develop-cclinks" / "s.jsonl", [user("hi")])
        assert session_info(path).project == "cclinks"

    def test_unreadable_transcript_still_yields_an_identity(self, tmp_path):
        """A row must never lose its origin just because the file went away."""
        info = session_info(tmp_path / "-Users-me-develop-x" / "gone.jsonl")
        assert info.session_id == "gone"
        assert info.title is None

    def test_tolerates_broken_lines(self, tmp_path):
        path = tmp_path / "s.jsonl"
        path.write_text(
            "{not json\n" + json.dumps({"type": "ai-title", "aiTitle": "ok"}) + "\n",
            encoding="utf-8",
        )
        assert session_info(path).title == "ok"

    def test_carries_the_modification_time(self, tmp_path):
        path = write(tmp_path / "s.jsonl", [user("hi")])
        os.utime(path, (1000, 4242))
        assert session_info(path).mtime == 4242


class TestSessionLabel:
    def test_titled_session_reads_as_project_and_title(self):
        info = SessionInfo(session_id="a98d5202-6e0e", project="cclinks", title="出自表示")
        assert info.label == "cclinks/出自表示"

    def test_untitled_session_falls_back_to_a_short_id(self):
        info = SessionInfo(session_id="a98d5202-6e0e-4beb", project="cclinks")
        assert info.label == "cclinks/a98d5202"


def project_with(tmp_path, encoded, names, mtimes):
    directory = tmp_path / encoded
    directory.mkdir(parents=True, exist_ok=True)
    made = []
    for name, mtime in zip(names, mtimes):
        path = directory / f"{name}.jsonl"
        path.write_text("{}\n", encoding="utf-8")
        os.utime(path, (mtime, mtime))
        made.append(path)
    return made


class TestListing:
    """The gap the feedback pointed at: one transcript per project was all we read."""

    def test_every_session_of_every_project_newest_first(self, tmp_path):
        project_with(tmp_path, "-Users-me-a", ["a1", "a2"], [1000, 3000])
        project_with(tmp_path, "-Users-me-b", ["b1"], [2000])
        found = all_transcripts(projects_dir=tmp_path)
        assert [path.stem for path in found] == ["a2", "b1", "a1"]

    def test_every_session_of_one_project(self, tmp_path):
        project_with(tmp_path, "-Users-me-a", ["a1", "a2"], [1000, 3000])
        project_with(tmp_path, "-Users-me-b", ["b1"], [2000])
        found = transcripts_for_cwd("/Users/me/a", projects_dir=tmp_path)
        assert [path.stem for path in found] == ["a2", "a1"]

    def test_unknown_project_has_no_sessions(self, tmp_path):
        project_with(tmp_path, "-Users-me-a", ["a1"], [1000])
        assert transcripts_for_cwd("/no/such/dir", projects_dir=tmp_path) == []

    def test_missing_root_is_not_an_error(self, tmp_path):
        assert all_transcripts(projects_dir=tmp_path / "nope") == []

    def test_scope_all_ignores_the_working_directory(self, tmp_path, monkeypatch):
        project_with(tmp_path, "-Users-me-a", ["a1"], [1000])
        project_with(tmp_path, "-Users-me-b", ["b1"], [2000])
        monkeypatch.setattr("cclinks.sources.claude_code._DEFAULT_PROJECTS", tmp_path)
        assert len(list_transcripts("/Users/me/a", scope="all")) == 2

    def test_scope_project_keeps_to_the_working_directory(self, tmp_path, monkeypatch):
        project_with(tmp_path, "-Users-me-a", ["a1"], [1000])
        project_with(tmp_path, "-Users-me-b", ["b1"], [2000])
        monkeypatch.setattr("cclinks.sources.claude_code._DEFAULT_PROJECTS", tmp_path)
        found = list_transcripts("/Users/me/a", scope="project")
        assert [path.stem for path in found] == ["a1"]
