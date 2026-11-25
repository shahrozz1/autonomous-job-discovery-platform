"""Greenhouse Job Board API: https://docs.greenhouse.io/job-board.html

The list has no descriptions, so they are fetched one at a time, and only for new postings whose
title matches. On a normal day that is a handful of requests instead of thousands.
"""

from __future__ import annotations

from ..extract import yearly_range
from ..models import Posting
from ..places import is_vague
from ..text import html_to_text, squash
from .base import Source, day

_API = "https://boards-api.greenhouse.io/v1/boards"


class Greenhouse(Source):
    platform = "greenhouse"

    def list_url(self, board: str) -> str:
        return f"{_API}/{board}/jobs"

    def parse_list(self, payload, board, company):
        return [
            Posting(
                platform=self.platform,
                board=board,
                source_id=str(job["id"]),
                company=company or squash(job.get("company_name") or board),
                title=squash(job["title"]),
                url=job["absolute_url"],
                location=squash((job.get("location") or {}).get("name") or ""),
                posted_at=day(job.get("first_published")),
                updated_at=job.get("updated_at"),
            )
            for job in payload.get("jobs", [])
        ]

    def detail_url(self, posting):
        return f"{_API}/{posting.board}/jobs/{posting.source_id}?pay_transparency=true"

    def parse_detail(self, payload, posting):
        posting.description = html_to_text(payload.get("content"))
        departments = [d["name"] for d in payload.get("departments") or [] if d.get("name")]
        posting.department = squash(departments[0]) if departments else None
        if is_vague(posting.location):  # "Hybrid" is not a place; the office list usually has one
            offices = [o.get("location") or o.get("name") for o in payload.get("offices") or []]
            posting.location = "; ".join(squash(o) for o in offices if o) or posting.location
        ranges = [r for r in payload.get("pay_input_ranges") or [] if r.get("currency_type") == "USD"]
        if ranges:  # several ranges mean several levels or cities; use the first one listed
            posting.pay_min, posting.pay_max = yearly_range(ranges[0]["min_cents"] / 100, ranges[0]["max_cents"] / 100)
