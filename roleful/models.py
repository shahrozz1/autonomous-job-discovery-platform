"""The one record type every source produces, whatever shape its feed has."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Posting:
    platform: str
    board: str
    source_id: str
    company: str
    title: str
    url: str
    location: str = ""  # every location in the feed, joined with "; "
    country: str | None = None
    workplace: str | None = None  # remote, hybrid or onsite, when the feed says so
    department: str | None = None
    employment: str | None = None
    posted_at: str | None = None  # ISO date
    updated_at: str | None = None
    pay_min: float | None = None  # yearly dollars, when the feed lists pay as data
    pay_max: float | None = None
    description: str | None = None  # plain text; None means it has to be fetched separately

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.platform, self.board, self.source_id)
