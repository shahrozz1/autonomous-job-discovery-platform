"""What every source has to provide. Parsing is kept apart from fetching so it can be tested
without the network."""

from __future__ import annotations

from datetime import UTC, datetime

from ..models import Posting


class Source:
    platform = ""

    def list_url(self, board: str) -> str:
        raise NotImplementedError

    def parse_list(self, payload, board: str, company: str) -> list[Posting]:
        raise NotImplementedError

    def detail_url(self, posting: Posting) -> str | None:
        """Where to get the description, for feeds that leave it out of the list."""
        return None

    def parse_detail(self, payload, posting: Posting) -> None:
        """Fill in the fields that only the detail feed has."""


def day(value: str | int | None) -> str | None:
    """ISO text or a millisecond timestamp, as a plain YYYY-MM-DD date."""
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return datetime.fromtimestamp(value / 1000, UTC).date().isoformat()
    return str(value)[:10]
