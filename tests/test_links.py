"""Link extraction tests.

Claude Code draws a Markdown link as its label alone, so the URL never reaches
the terminal buffer. Only the transcript still holds it, so that is what is parsed.
"""

from cclinks.links import Link, extract_links


def urls(text):
    return [link.url for link in extract_links(text)]


class TestMarkdownLinks:
    def test_extracts_url_and_label(self):
        (link,) = extract_links("see [MathRender](https://example.com/mr) for details")
        assert link.url == "https://example.com/mr"
        assert link.label == "MathRender"

    def test_extracts_multiple(self):
        text = "[A](https://a.example) and [B](https://b.example)"
        assert urls(text) == ["https://a.example", "https://b.example"]

    def test_label_may_contain_spaces_and_multibyte_text(self):
        (link,) = extract_links("[前回書いた記事](https://example.com/x)")
        assert link.label == "前回書いた記事"

    def test_ignores_non_http_targets(self):
        assert urls("[file](./local/path.md) and [anchor](#section)") == []

    def test_label_does_not_swallow_an_enclosing_bracket(self):
        """A link inside a JSON array must not take the array's bracket as its label."""
        text = '{"content": [{"text": "see [OpenAI](https://openai.com/)"}]}'
        (link,) = extract_links(text)
        assert link.label == "OpenAI"
        assert link.url == "https://openai.com/"

    def test_handles_url_with_parentheses_in_path(self):
        (link,) = extract_links("[wiki](https://en.wikipedia.org/wiki/Foo_(bar))")
        assert link.url == "https://en.wikipedia.org/wiki/Foo_(bar)"


class TestBareUrls:
    def test_extracts_bare_url(self):
        (link,) = extract_links("look at https://example.com/plain")
        assert link.url == "https://example.com/plain"

    def test_bare_url_uses_url_as_label(self):
        (link,) = extract_links("https://example.com/plain")
        assert link.label == "https://example.com/plain"

    def test_strips_trailing_punctuation(self):
        assert urls("see https://example.com/x。") == ["https://example.com/x"]
        assert urls("(https://example.com/y)") == ["https://example.com/y"]

    def test_does_not_double_count_markdown_target(self):
        assert urls("[A](https://a.example)") == ["https://a.example"]


class TestNoise:
    """Text that merely looks like a URL must not be picked up."""

    def test_ignores_scheme_only(self):
        assert urls("a URL such as `https://`") == []

    def test_ignores_host_without_dot(self):
        assert urls("https://localhostish") == []

    def test_strips_trailing_backtick(self):
        assert urls("`https://example.com/x`") == ["https://example.com/x"]

    def test_strips_trailing_backslash(self):
        # Shell escaping can leave one behind.
        assert urls("https://example.com/x\\") == ["https://example.com/x"]

    def test_ignores_elided_url(self):
        # An abbreviation such as "https://marketplace..." is not a link.
        assert urls("I wrote `[A](https://marketplace...)`") == []

    def test_keeps_real_url_next_to_noise(self):
        text = "`https://` is not one, https://example.com/ok is"
        assert urls(text) == ["https://example.com/ok"]

    def test_allows_localhost_with_port(self):
        assert urls("http://localhost:8080/health") == ["http://localhost:8080/health"]


class TestDedup:
    def test_dedupes_same_url(self):
        assert urls("[A](https://a.example) and [again](https://a.example)") == [
            "https://a.example"
        ]

    def test_keeps_first_label_on_dedup(self):
        (link,) = extract_links("[first](https://a.example) [second](https://a.example)")
        assert link.label == "first"

    def test_label_wins_over_bare_url(self):
        """When a URL also appears bare, the labelled occurrence is kept."""
        (link,) = extract_links("https://a.example is what we call [Article A](https://a.example)")
        assert link.label == "Article A"

    def test_label_wins_regardless_of_order(self):
        (link,) = extract_links("[Article A](https://a.example) is https://a.example")
        assert link.label == "Article A"

    def test_position_follows_first_occurrence(self):
        # Adopting a later label must not reorder the list.
        links = extract_links("https://a.example and [B](https://b.example) and [A](https://a.example)")
        assert [link.url for link in links] == ["https://a.example", "https://b.example"]


class TestTypes:
    def test_returns_link_objects(self):
        assert all(isinstance(link, Link) for link in extract_links("https://a.example"))

    def test_empty_text(self):
        assert extract_links("") == []

    def test_text_without_links(self):
        assert extract_links("a sentence with no links") == []
