"""Tests for the source-independent half: message texts in, links out."""

from dataclasses import replace

from cclinks.collect import links_for_session, links_from_texts, sourced_links
from cclinks.sources.base import SessionInfo, Source


class TestLinksFromTexts:
    def test_keeps_the_order_it_is_given(self):
        texts = ["[new](https://new.example)", "[old](https://old.example)"]
        assert [link.url for link in links_from_texts(texts)] == [
            "https://new.example",
            "https://old.example",
        ]

    def test_preserves_order_within_a_text(self):
        texts = ["[a](https://a.example) [b](https://b.example)"]
        assert [link.url for link in links_from_texts(texts)] == [
            "https://a.example",
            "https://b.example",
        ]

    def test_dedupes_across_texts_keeping_the_first(self):
        texts = ["[newer name](https://same.example)", "[older name](https://same.example)"]
        (link,) = links_from_texts(texts)
        assert link.label == "newer name"

    def test_label_survives_a_bare_mention_seen_first(self):
        """Pasted output repeats URLs without labels; the label must not be lost."""
        texts = ["```\nhttps://docs.example/x\n```", "[the docs](https://docs.example/x)"]
        (link,) = links_from_texts(texts)
        assert link.label == "the docs"

    def test_empty_input(self):
        assert links_from_texts([]) == []

    def test_texts_without_links(self):
        assert links_from_texts(["nothing here", "nor here"]) == []


def fake_source(transcript, texts):
    return Source(
        name="fake",
        find_transcript=lambda cwd: transcript,
        message_texts=lambda path: texts,
    )


class TestLinksForSession:
    def test_reads_through_the_source(self):
        source = fake_source("/some/transcript.jsonl", ["[A](https://a.example)"])
        assert [link.url for link in links_for_session(None, source)] == ["https://a.example"]

    def test_no_transcript_means_no_links(self):
        source = fake_source(None, ["[A](https://a.example)"])
        assert links_for_session(None, source) == []

    def test_cwd_is_handed_to_the_source(self):
        seen = {}

        source = Source(
            name="fake",
            find_transcript=lambda cwd: seen.setdefault("cwd", cwd) or None,
            message_texts=lambda path: [],
        )
        links_for_session("/here", source)
        assert seen["cwd"] == "/here"


def transcripts(spec):
    """A fake source over `spec`: {name: (mtime, [texts...])}, newest first."""
    order = sorted(spec, key=lambda name: spec[name][0], reverse=True)
    return Source(
        name="fake",
        find_transcript=lambda cwd: order[0] if order else None,
        message_texts=lambda path: spec[path][1],
        list_transcripts=lambda cwd, scope: list(order),
        session_info=lambda path: SessionInfo(
            session_id=path, project=path, title=path, mtime=spec[path][0]
        ),
    )


class TestSourcedLinks:
    """Links from many sessions at once, each still knowing where it came from."""

    def test_gathers_every_session(self):
        source = transcripts(
            {
                "older": (1000, ["[a](https://a.example)"]),
                "newer": (2000, ["[b](https://b.example)"]),
            }
        )
        found = sourced_links(None, source)
        assert [item.link.url for item in found] == ["https://b.example", "https://a.example"]

    def test_each_link_carries_its_session(self):
        source = transcripts(
            {
                "older": (1000, ["[a](https://a.example)"]),
                "newer": (2000, ["[b](https://b.example)"]),
            }
        )
        found = sourced_links(None, source)
        assert [item.session.session_id for item in found] == ["newer", "older"]

    def test_session_order_is_newest_first(self):
        source = transcripts(
            {
                "mid": (2000, ["[m](https://m.example)"]),
                "old": (1000, ["[o](https://o.example)"]),
                "new": (3000, ["[n](https://n.example)"]),
            }
        )
        assert [item.session.session_id for item in sourced_links(None, source)] == [
            "new",
            "mid",
            "old",
        ]

    def test_order_within_a_session_is_kept(self):
        source = transcripts({"only": (1000, ["[a](https://a.example) [b](https://b.example)"])})
        assert [item.link.url for item in sourced_links(None, source)] == [
            "https://a.example",
            "https://b.example",
        ]

    def test_a_url_seen_twice_keeps_the_newer_session(self):
        """The same URL in two sessions is one row, attributed to the one in front of you."""
        source = transcripts(
            {
                "older": (1000, ["[old name](https://same.example)"]),
                "newer": (2000, ["[new name](https://same.example)"]),
            }
        )
        (item,) = sourced_links(None, source)
        assert item.session.session_id == "newer"
        assert item.link.label == "new name"

    def test_a_bare_url_does_not_lose_a_label_from_an_older_session(self):
        source = transcripts(
            {
                "older": (1000, ["[the docs](https://docs.example/x)"]),
                "newer": (2000, ["```\nhttps://docs.example/x\n```"]),
            }
        )
        (item,) = sourced_links(None, source)
        assert item.link.label == "the docs"
        assert item.session.session_id == "newer"

    def test_limit_caps_the_number_of_sessions(self):
        source = transcripts(
            {
                "old": (1000, ["[o](https://o.example)"]),
                "mid": (2000, ["[m](https://m.example)"]),
                "new": (3000, ["[n](https://n.example)"]),
            }
        )
        found = sourced_links(None, source, limit=2)
        assert [item.session.session_id for item in found] == ["new", "mid"]

    def test_limit_zero_means_every_session(self):
        source = transcripts(
            {
                "old": (1000, ["[o](https://o.example)"]),
                "new": (2000, ["[n](https://n.example)"]),
            }
        )
        assert len(sourced_links(None, source, limit=0)) == 2

    def test_since_drops_sessions_that_are_too_old(self):
        source = transcripts(
            {
                "stale": (1000, ["[o](https://o.example)"]),
                "fresh": (9000, ["[n](https://n.example)"]),
            }
        )
        found = sourced_links(None, source, since=2000, now=10000)
        assert [item.session.session_id for item in found] == ["fresh"]

    def test_since_none_keeps_everything(self):
        source = transcripts(
            {
                "stale": (1000, ["[o](https://o.example)"]),
                "fresh": (9000, ["[n](https://n.example)"]),
            }
        )
        assert len(sourced_links(None, source, since=None, now=10000)) == 2

    def test_scope_session_reads_one_transcript_only(self):
        source = transcripts(
            {
                "older": (1000, ["[a](https://a.example)"]),
                "newer": (2000, ["[b](https://b.example)"]),
            }
        )
        found = sourced_links(None, source, scope="session")
        assert [item.link.url for item in found] == ["https://b.example"]

    def test_scope_is_handed_to_the_source(self):
        seen = {}
        source = Source(
            name="fake",
            find_transcript=lambda cwd: None,
            message_texts=lambda path: [],
            list_transcripts=lambda cwd, scope: seen.update(cwd=cwd, scope=scope) or [],
        )
        sourced_links("/here", source, scope="project")
        assert seen == {"cwd": "/here", "scope": "project"}

    def test_active_record_pins_the_session(self):
        source = transcripts(
            {
                "background": (9000, ["[b](https://background.example)"]),
                "typed-into": (1000, ["[t](https://typed.example)"]),
            }
        )
        source = replace(source, active_transcript=lambda: "typed-into")
        found = sourced_links(None, source, active=True)
        assert [item.link.url for item in found] == ["https://typed.example"]

    def test_a_source_that_cannot_list_still_works(self):
        """An older source only knows how to find one transcript."""
        source = Source(
            name="minimal",
            find_transcript=lambda cwd: "only",
            message_texts=lambda path: ["[a](https://a.example)"],
        )
        found = sourced_links(None, source)
        assert [item.link.url for item in found] == ["https://a.example"]

    def test_a_source_without_session_info_still_names_the_session(self):
        source = Source(
            name="minimal",
            find_transcript=lambda cwd: "/tmp/some-session.jsonl",
            message_texts=lambda path: ["[a](https://a.example)"],
        )
        (item,) = sourced_links(None, source)
        assert item.session.session_id == "some-session"

    def test_no_sessions_means_no_links(self):
        source = Source(
            name="empty",
            find_transcript=lambda cwd: None,
            message_texts=lambda path: [],
            list_transcripts=lambda cwd, scope: [],
        )
        assert sourced_links(None, source) == []
