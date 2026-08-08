"""Tests for the source-independent half: message texts in, links out."""

from cclinks.collect import links_for_session, links_from_texts
from cclinks.sources.base import Source


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
