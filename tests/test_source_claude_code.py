"""Claude Code source tests: finding a transcript and reading messages out of it."""

import json
import os

from cclinks.sources import claude_code
from cclinks.sources.claude_code import (
    find_transcript,
    latest_transcript,
    message_texts,
    transcript_for_cwd,
)


def write(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return str(path)


def assistant(text):
    return {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


def user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


class TestMessageTexts:
    def test_newest_message_first(self, tmp_path):
        path = write(tmp_path / "t.jsonl", [assistant("older"), assistant("newer")])
        assert message_texts(path) == ["newer", "older"]

    def test_includes_user_messages(self, tmp_path):
        path = write(tmp_path / "t.jsonl", [user("from the user")])
        assert message_texts(path) == ["from the user"]

    def test_joins_text_blocks_of_one_message(self, tmp_path):
        row = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "first"},
                    {"type": "tool_use", "name": "Bash"},
                    {"type": "text", "text": "second"},
                ],
            },
        }
        path = write(tmp_path / "t.jsonl", [row])
        assert message_texts(path) == ["first\nsecond"]

    def test_skips_messages_without_text(self, tmp_path):
        tool_only = {
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Bash"}]},
        }
        path = write(tmp_path / "t.jsonl", [assistant("kept"), tool_only])
        assert message_texts(path) == ["kept"]

    def test_skips_sidechain(self, tmp_path):
        row = assistant("subagent")
        row["isSidechain"] = True
        path = write(tmp_path / "t.jsonl", [row, assistant("main")])
        assert message_texts(path) == ["main"]

    def test_tolerates_broken_lines(self, tmp_path):
        path = tmp_path / "t.jsonl"
        path.write_text("{not json\n" + json.dumps(assistant("ok")) + "\n", encoding="utf-8")
        assert message_texts(str(path)) == ["ok"]

    def test_missing_file_returns_empty(self, tmp_path):
        assert message_texts(str(tmp_path / "none.jsonl")) == []


class TestTranscriptForCwd:
    def test_finds_newest_transcript_for_the_directory(self, tmp_path):
        projects = tmp_path / "projects"
        encoded = projects / "-Users-me-develop"
        encoded.mkdir(parents=True)
        old = encoded / "old.jsonl"
        new = encoded / "new.jsonl"
        old.write_text("{}\n", encoding="utf-8")
        new.write_text("{}\n", encoding="utf-8")
        os.utime(old, (1000, 1000))
        os.utime(new, (2000, 2000))
        assert transcript_for_cwd("/Users/me/develop", projects_dir=projects) == new

    def test_returns_none_when_no_transcript(self, tmp_path):
        assert transcript_for_cwd("/Users/me/develop", projects_dir=tmp_path) is None

    def test_encodes_slashes_as_dashes(self, tmp_path):
        projects = tmp_path / "projects"
        encoded = projects / "-Users-me-develop-sub"
        encoded.mkdir(parents=True)
        target = encoded / "s.jsonl"
        target.write_text("{}\n", encoding="utf-8")
        assert transcript_for_cwd("/Users/me/develop/sub", projects_dir=projects) == target

    def test_falls_back_to_newest_session_anywhere(self, tmp_path):
        """With no session for this directory, use the newest one anywhere.

        A launcher's working directory is arbitrary, and the session being
        looked at is almost always the one updated last.
        """
        projects = tmp_path / "projects"
        (projects / "-Users-me-other").mkdir(parents=True)
        (projects / "-Users-me-another").mkdir(parents=True)
        old = projects / "-Users-me-other" / "old.jsonl"
        new = projects / "-Users-me-another" / "new.jsonl"
        old.write_text("{}\n", encoding="utf-8")
        new.write_text("{}\n", encoding="utf-8")
        os.utime(old, (1000, 1000))
        os.utime(new, (2000, 2000))
        assert transcript_for_cwd("/no/such/dir", projects_dir=projects, fallback=True) == new

    def test_fallback_is_opt_in(self, tmp_path):
        projects = tmp_path / "projects"
        (projects / "-Users-me-other").mkdir(parents=True)
        (projects / "-Users-me-other" / "s.jsonl").write_text("{}\n", encoding="utf-8")
        assert transcript_for_cwd("/no/such/dir", projects_dir=projects) is None

    def test_prefers_exact_match_over_fallback(self, tmp_path):
        projects = tmp_path / "projects"
        (projects / "-Users-me-develop").mkdir(parents=True)
        (projects / "-Users-me-other").mkdir(parents=True)
        mine = projects / "-Users-me-develop" / "mine.jsonl"
        newer = projects / "-Users-me-other" / "newer.jsonl"
        mine.write_text("{}\n", encoding="utf-8")
        newer.write_text("{}\n", encoding="utf-8")
        os.utime(mine, (1000, 1000))
        os.utime(newer, (9000, 9000))
        assert transcript_for_cwd("/Users/me/develop", projects_dir=projects, fallback=True) == mine


class TestLatestTranscript:
    def test_returns_the_most_recently_updated(self, tmp_path):
        projects = tmp_path / "projects"
        (projects / "-a").mkdir(parents=True)
        (projects / "-b").mkdir(parents=True)
        old = projects / "-a" / "old.jsonl"
        new = projects / "-b" / "new.jsonl"
        old.write_text("{}\n", encoding="utf-8")
        new.write_text("{}\n", encoding="utf-8")
        os.utime(old, (1000, 1000))
        os.utime(new, (2000, 2000))
        assert latest_transcript(projects_dir=projects) == new

    def test_returns_none_when_root_is_missing(self, tmp_path):
        assert latest_transcript(projects_dir=tmp_path / "nope") is None

    def test_returns_none_when_empty(self, tmp_path):
        assert latest_transcript(projects_dir=tmp_path) is None


class TestFindTranscript:
    def test_none_cwd_means_latest(self, monkeypatch):
        monkeypatch.setattr(claude_code, "latest_transcript", lambda: "LATEST")
        assert find_transcript(None) == "LATEST"

    def test_a_cwd_is_looked_up_with_fallback(self, monkeypatch):
        seen = {}

        def fake(cwd, fallback=False):
            seen["cwd"] = cwd
            seen["fallback"] = fallback
            return "FOUND"

        monkeypatch.setattr(claude_code, "transcript_for_cwd", fake)
        assert find_transcript("/somewhere") == "FOUND"
        assert seen == {"cwd": "/somewhere", "fallback": True}
