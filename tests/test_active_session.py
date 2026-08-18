"""Reading the session the user last typed into.

A picker launched from an editor hotkey is not a child of Claude Code, so it
never sees CLAUDE_CODE_SESSION_ID. Choosing the transcript with the newest
mtime instead picks whichever session merely wrote last, which is often another
tab grinding through a long task in the background. A UserPromptSubmit hook
records the session being typed into; these tests cover reading that record.
"""

import json

import pytest

from cclinks import cli
from cclinks.collect import sourced_links
from cclinks.sources import Source, claude_code
from cclinks.sources.claude_code import active_transcript


def record(path, **fields):
    path.write_text(json.dumps(fields), encoding="utf-8")
    return path


class TestActiveTranscript:
    def test_uses_the_recorded_transcript(self, tmp_path):
        transcript = tmp_path / "a49eed97.jsonl"
        transcript.write_text("{}\n", encoding="utf-8")
        active = record(tmp_path / "active.json", transcript_path=str(transcript))
        assert active_transcript(active_file=active) == transcript

    def test_prefers_the_record_over_the_newest_session(self, tmp_path):
        """The whole point: the newest file is not necessarily the one in front of you."""
        projects = tmp_path / "projects"
        (projects / "-Users-me-develop").mkdir(parents=True)
        typed_into = projects / "-Users-me-develop" / "mine.jsonl"
        background = projects / "-Users-me-develop" / "other.jsonl"
        typed_into.write_text("{}\n", encoding="utf-8")
        background.write_text("{}\n", encoding="utf-8")
        import os

        os.utime(typed_into, (1000, 1000))
        os.utime(background, (2000, 2000))

        active = record(tmp_path / "active.json", transcript_path=str(typed_into))
        assert active_transcript(active_file=active, projects_dir=projects) == typed_into

    def test_falls_back_to_the_recorded_cwd(self, tmp_path):
        """A rotated or deleted transcript should not lose the session entirely."""
        projects = tmp_path / "projects"
        (projects / "-Users-me-develop").mkdir(parents=True)
        surviving = projects / "-Users-me-develop" / "still-here.jsonl"
        surviving.write_text("{}\n", encoding="utf-8")
        active = record(
            tmp_path / "active.json",
            transcript_path=str(tmp_path / "gone.jsonl"),
            cwd="/Users/me/develop",
        )
        assert active_transcript(active_file=active, projects_dir=projects) == surviving

    def test_returns_none_without_a_record(self, tmp_path):
        """No hook installed yet: the caller decides what to do instead."""
        assert active_transcript(active_file=tmp_path / "missing.json") is None

    def test_returns_none_on_a_corrupt_record(self, tmp_path):
        broken = tmp_path / "active.json"
        broken.write_text("{not json", encoding="utf-8")
        assert active_transcript(active_file=broken) is None

    def test_returns_none_when_nothing_is_resolvable(self, tmp_path):
        active = record(tmp_path / "active.json", session_id="abc")
        assert active_transcript(active_file=active, projects_dir=tmp_path) is None


class TestReadingTheActiveSession:
    def test_active_record_is_used_when_asked(self, tmp_path, monkeypatch):
        transcript = tmp_path / "mine.jsonl"
        transcript.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "see [docs](https://a.example)"}],
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        active = record(tmp_path / "active.json", transcript_path=str(transcript))
        monkeypatch.setattr(claude_code, "_active_file", lambda: active)

        found = sourced_links(None, active=True)
        assert [item.link.url for item in found] == ["https://a.example"]

    def test_falls_back_when_there_is_no_record(self):
        """Without the hook, --active must still behave like --latest."""
        called = {}
        unrecorded = Source(
            name="test",
            find_transcript=lambda cwd: called.setdefault("cwd", cwd),
            message_texts=lambda path: [],
            active_transcript=lambda: None,
        )
        sourced_links(None, unrecorded, active=True)
        assert "cwd" in called


class TestCliActiveFlag:
    @pytest.fixture
    def collector(self, monkeypatch):
        seen = {}

        def fake_collect(cwd, **kwargs):
            seen["cwd"] = cwd
            seen.update(kwargs)
            return []

        monkeypatch.setattr(cli, "collect_links", fake_collect)
        monkeypatch.setattr(cli, "find_fzf", lambda: "/usr/bin/fzf")
        monkeypatch.setattr(cli, "choose", lambda lines, header=None: None)
        return seen

    def test_active_is_requested(self, collector):
        cli.main(["--active"])
        assert collector["active"] is True

    def test_active_does_not_consult_the_working_directory(self, collector):
        """The hotkey's working directory is arbitrary; the record is authoritative."""
        cli.main(["--active"])
        assert collector["cwd"] is None

    def test_active_reads_one_session_only(self, collector):
        """The record names a session; widening past it would defeat the point."""
        cli.main(["--active"])
        assert collector["scope"] == "session"

    def test_default_does_not_request_it(self, collector):
        cli.main([])
        assert collector["active"] is False
