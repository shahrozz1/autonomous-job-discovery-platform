"""Decide which postings are worth reading, from the title alone."""

from __future__ import annotations

import re
import tomllib
from functools import cached_property
from pathlib import Path


class Profile:
    """What to look for, loaded from config/profile.toml."""

    def __init__(self, settings: dict):
        self.settings = settings
        self.candidate = settings["candidate"]
        self.points = settings["score"]

    @classmethod
    def load(cls, path: Path) -> Profile:
        return cls(tomllib.loads(path.read_text(encoding="utf-8")))

    @cached_property
    def _skip(self) -> list[re.Pattern]:
        return [re.compile(p, re.I) for p in self.settings["titles"]["skip"]]

    @cached_property
    def _families(self) -> list[tuple[str, list[re.Pattern]]]:
        return [
            (family["name"], [re.compile(p, re.I) for p in family["match"]])
            for family in self.settings["titles"]["family"]
        ]

    def family(self, title: str) -> str | None:
        """The job family a title belongs to, or None when it isn't a match."""
        if any(pattern.search(title) for pattern in self._skip):
            return None
        for name, patterns in self._families:
            if any(pattern.search(title) for pattern in patterns):
                return name
        return None


def title_key(title: str) -> str:
    """The part of a title that says what the job is, so the same job in two cities matches.

    "Data Analyst (Remote)" and "Data Analyst - Dallas, TX" both become "data analyst".
    """
    text = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", title.lower())
    text = re.sub(r"\s[-–—|]\s.*?(remote|hybrid|onsite|[a-z ]+, [a-z]{2})\s*$", " ", text)
    text = re.sub(r"\bjr\b\.?", "junior", text)
    return re.sub(r"[^a-z0-9&+]+", " ", text).strip()
