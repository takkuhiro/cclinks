"""Extract URLs from text.

Claude Code draws a Markdown link as its label alone, so the URL never reaches
the terminal buffer. The raw transcript text still has it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["Link", "extract_links", "merge_links"]


@dataclass(frozen=True)
class Link:
    url: str
    label: str


# [label](url). One level of balanced parentheses is allowed inside the URL.
# The label cannot contain a bracket of its own: a link sitting inside a JSON
# array would otherwise be matched from the array's opening bracket.
_MARKDOWN = re.compile(r"\[([^\[\]]*)\]\(\s*(https?://(?:[^\s()]|\([^\s()]*\))+)\s*\)")
# CJK brackets are excluded as well: prose often wraps a URL in them without a space.
_BARE = re.compile(r"https?://(?:[^\s()<>\[\]「」『』]|\([^\s()]*\))+")

# Sentence punctuation, closing brackets and code-span markers are not part of a URL.
# The CJK marks matter because Japanese text puts them straight after a URL, unspaced.
_TRAILING = "。、.,;:!?)\"'”』」>`\\"

# A plausible host: dotted, or a bare name with a port.
_HOSTLIKE = re.compile(
    r"^https?://[^/\s:]+(?:\.[^/\s:]+)+(?::\d+)?(?:[/?#]|$)"
    r"|^https?://[^/\s:]+:\d+(?:[/?#]|$)"
)


def _is_hostlike(url: str) -> bool:
    """Reject prose such as a lone `https://` or an elided `https://example...`."""
    return bool(_HOSTLIKE.match(url))


def _clean(url: str) -> str:
    """Drop trailing punctuation.

    A closing parenthesis can belong to the URL (Wikipedia disambiguation, for
    one), so it is dropped only when it is unbalanced.
    """
    while url and url[-1] in _TRAILING:
        if url[-1] == ")" and url.count("(") >= url.count(")"):
            break
        url = url[:-1]
    return url


def merge_links(existing: list[Link], incoming) -> None:
    """Append links to `existing`, in place, skipping duplicates.

    A URL keeps the position of its first occurrence. A later occurrence only
    matters when it carries a label and the stored one does not: pasted command
    output can mention a URL bare, and that must not erase the label.
    """
    index = {link.url: position for position, link in enumerate(existing)}
    for link in incoming:
        position = index.get(link.url)
        if position is None:
            index[link.url] = len(existing)
            existing.append(link)
            continue
        stored = existing[position]
        if stored.label == stored.url and link.label != link.url:
            existing[position] = link


def extract_links(text: str) -> list[Link]:
    if not text:
        return []

    found: list[tuple[int, Link]] = []
    markdown_spans: list[tuple[int, int]] = []

    for match in _MARKDOWN.finditer(text):
        url = _clean(match.group(2))
        if _is_hostlike(url):
            found.append((match.start(), Link(url=url, label=match.group(1).strip() or url)))
        markdown_spans.append((match.start(), match.end()))

    for match in _BARE.finditer(text):
        # Already counted as the target of a Markdown link.
        if any(start <= match.start() < end for start, end in markdown_spans):
            continue
        url = _clean(match.group(0))
        if _is_hostlike(url):
            found.append((match.start(), Link(url=url, label=url)))

    found.sort(key=lambda pair: pair[0])

    result: list[Link] = []
    merge_links(result, (link for _, link in found))
    return result
