"""Find postings that are really the same job.

Companies list one job several times: once per city, once per store, or again when the first
listing expires. Two postings count as the same job when they come from the same company, have the
same core title ("Operations Coordinator" for both "Operations Coordinator (Soho)" and "Operations
Coordinator (Legacy West)"), and their descriptions share most of their wording.

How much is "most" depends on the titles. Company boilerplate alone can make two different jobs look
70% alike, so when the full titles differ the descriptions have to be almost identical.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

# Share of five-word phrases two descriptions must have in common.
SAME_TITLE = 0.70
SAME_CORE_TITLE = 0.90


@dataclass(frozen=True)
class Item:
    posting_id: int
    company: str
    title: str
    title_key: str
    description: str


def phrases(text: str, size: int = 5) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z]+", text.lower())
    return {tuple(words[i : i + size]) for i in range(len(words) - size + 1)}


def similarity(a: set, b: set) -> float:
    """Jaccard similarity: shared phrases over all phrases."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def group(items: list[Item]) -> dict[int, int]:
    """Map each posting_id to the role it belongs to (the lowest posting_id in its group)."""
    parent = {item.posting_id: item.posting_id for item in items}

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    buckets: dict[tuple[str, str], list[Item]] = defaultdict(list)
    for item in items:
        buckets[(item.company.lower(), item.title_key)].append(item)

    for bucket in buckets.values():  # only postings that could match are ever compared
        prints = {item.posting_id: phrases(item.description) for item in bucket}
        for i, a in enumerate(bucket):
            for b in bucket[i + 1 :]:
                needed = SAME_TITLE if a.title.lower() == b.title.lower() else SAME_CORE_TITLE
                if similarity(prints[a.posting_id], prints[b.posting_id]) >= needed:
                    low, high = sorted((root(a.posting_id), root(b.posting_id)))
                    parent[high] = low
    return {item.posting_id: root(item.posting_id) for item in items}
