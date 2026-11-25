"""Ashby public job posting API: https://developers.ashbyhq.com/docs/public-job-posting-api"""

from __future__ import annotations

from ..extract import yearly_range
from ..models import Posting
from ..text import html_to_text, squash
from .base import Source, day

_WORKPLACE = {"Remote": "remote", "Hybrid": "hybrid", "OnSite": "onsite"}
_PERIODS = {"1 YEAR": 1, "1 MONTH": 12, "1 HOUR": 2080}


class Ashby(Source):
    platform = "ashby"

    def list_url(self, board: str) -> str:
        return f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true"

    def parse_list(self, payload, board, company):
        return [self._posting(job, board, company) for job in payload.get("jobs", []) if job.get("isListed", True)]

    def _posting(self, job, board, company) -> Posting:
        places = [job.get("location") or ""]
        places += [place.get("location") or "" for place in job.get("secondaryLocations") or []]
        address = (job.get("address") or {}).get("postalAddress") or {}
        posting = Posting(
            platform=self.platform,
            board=board,
            source_id=job["id"],
            company=company or board,
            title=squash(job["title"]),
            url=job["jobUrl"],
            location="; ".join(squash(p) for p in places if p),
            country=address.get("addressCountry"),
            workplace=_WORKPLACE.get(job.get("workplaceType") or ""),
            department=job.get("department"),
            employment=job.get("employmentType"),
            posted_at=day(job.get("publishedAt")),
            description=html_to_text(job.get("descriptionHtml")),
        )
        for part in (job.get("compensation") or {}).get("summaryComponents") or []:
            factor = _PERIODS.get(part.get("interval") or "")
            is_salary = part.get("compensationType") == "Salary" and part.get("currencyCode") == "USD"
            if is_salary and factor and part.get("minValue"):
                posting.pay_min, posting.pay_max = yearly_range(
                    part["minValue"] * factor, (part.get("maxValue") or part["minValue"]) * factor
                )
                break
        return posting
