"""Turn a posting's HTML into plain text that still shows its structure.

Headings come out as "# Heading" and list items as "- item", because where a skill is mentioned
(requirements, nice-to-haves, benefits) matters as much as whether it is mentioned.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

_BLOCKS = {"p", "div", "section", "article", "ul", "ol", "table", "tr", "br", "hr", "header", "footer"}
_HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_BOLD = {"b", "strong"}
_MAX_HEADING = 90


class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self._parts: list[tuple[str, bool]] = []  # (text, was it bold or in a heading tag)
        self._bold = 0
        self._bullet = False
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._skip += 1
        elif tag == "li":
            self._flush()
            self._bullet = True
        elif tag in _BLOCKS and not (self._bullet and not self._parts):
            self._flush()
        elif tag in _HEADINGS:
            self._flush()
            self._bold += 1
        elif tag in _BOLD:
            self._bold += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self._skip = max(0, self._skip - 1)
        elif tag in _BOLD:
            self._bold = max(0, self._bold - 1)
        elif tag in _HEADINGS:
            self._flush()
            self._bold = max(0, self._bold - 1)
        elif tag in _BLOCKS or tag == "li":
            self._flush()

    def handle_data(self, data):
        if not self._skip:
            self._parts.append((data, self._bold > 0))

    def close(self):
        super().close()
        self._flush()

    def _flush(self) -> None:
        text = squash("".join(part for part, _ in self._parts))
        if text:
            all_bold = all(bold for part, bold in self._parts if part.strip())
            if self._bullet:
                self.lines.append(f"- {text}")
            elif (all_bold or text.endswith(":")) and len(text) <= _MAX_HEADING:
                self.lines.append(f"# {text.rstrip(':')}")
            else:
                self.lines.append(text)
            self._bullet = False
        self._parts = []


def squash(text: str) -> str:
    """Collapse runs of whitespace (including non-breaking spaces) and trim."""
    return re.sub(r"\s+", " ", text.replace("​", "")).strip()


def html_to_text(markup: str | None) -> str:
    if not markup:
        return ""
    if "&lt;" in markup and "<p" not in markup:  # Greenhouse sends its HTML escaped
        markup = html.unescape(markup)
    reader = _Reader()
    reader.feed(markup)
    reader.close()
    return "\n".join(reader.lines)
