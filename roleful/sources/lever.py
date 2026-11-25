"""Lever Postings API: https://github.com/lever/postings-api"""

from __future__ import annotations

from ..extract import yearly_range
from ..models import Posting
from ..text import html_to_text, squash
from .base import Source, day

_WORKPLACE = {"remote": "remote", "hybrid": "hybrid", "on-site": "onsite", "onsite": "onsite"}
_PERIODS = {"per-year-salary": 1, "per-month-salary": 12, "per-hour-wage": 2080}


class Lever(Source):
    platform = "lever"

    def list_url(self, board: str) -> str:
        return f"https://api.lever.co/v0/postings/{board}?mode=json"

    def parse_list(self, payload, board, company):
        return [self._posting(job, board, company) for job in payload]

    def _posting(self, job, board, company) -> Posting:
        categories = job.get("categories") or {}
        places = categories.get("allLocations") or [categories.get("location") or ""]
        posting = Posting(
            platform=self.platform,
            board=board,
            source_id=job["id"],
            company=company or board,
            title=squash(job["text"]),
            url=job["hostedUrl"],
            location="; ".join(squash(p) for p in places if p),
            country=job.get("country"),
            workplace=_WORKPLACE.get(job.get("workplaceType") or ""),
            department=categories.get("department") or categories.get("team"),
            employment=categories.get("commitment"),
            posted_at=day(job.get("createdAt")),
            description=_description(job),
        )
        pay = job.get("salaryRange") or {}
        factor = _PERIODS.get(pay.get("interval") or "")
        if pay.get("currency") == "USD" and factor and pay.get("min"):
            posting.pay_min, posting.pay_max = yearly_range(
                pay["min"] * factor, (pay.get("max") or pay["min"]) * factor
            )
        return posting


def _description(job) -> str:
    """Lever splits a posting into an opening, a body, headed lists and a closing."""
    parts = [html_to_text(job.get("opening")), html_to_text(job.get("descriptionBody"))]
    if not any(parts):
        parts = [html_to_text(job.get("description"))]
    for block in job.get("lists") or []:
        parts.append(f"# {squash(block.get('text') or '').rstrip(':')}")
        parts.append(html_to_text(block.get("content")))
    parts.append(html_to_text(job.get("additional")))
    parts.append(html_to_text(job.get("salaryDescription")))
    return "\n".join(part for part in parts if part)
