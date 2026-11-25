"""A small, polite HTTP client for public job feeds.

One request at a time, a short pause between requests, retries with backoff when a platform is
busy, and ETag support so a board that hasn't changed since the last run costs almost nothing.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

import requests

USER_AGENT = "roleful/1.0 (reads public job board feeds)"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class FeedError(Exception):
    """A feed could not be read. The run carries on without it."""


@dataclass(frozen=True)
class Response:
    status: int
    data: object | None  # parsed JSON, or None when the server says "not modified" (304)
    etag: str | None


class Client:
    """Each platform gets its own client, so no platform ever sees two requests at once."""

    def __init__(self, pause: float = 0.15, retries: int = 3, timeout: float = 30.0):
        self.pause = pause
        self.retries = retries
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def get_json(self, url: str, etag: str | None = None) -> Response:
        headers = {"If-None-Match": etag} if etag else {}
        problem = "no attempt made"
        for attempt in range(self.retries + 1):
            time.sleep(self.pause)
            wait = 2**attempt + random.random()
            try:
                reply = self.session.get(url, headers=headers, timeout=self.timeout)
            except requests.RequestException as error:
                problem = type(error).__name__
            else:
                if reply.status_code == 304:
                    return Response(304, None, etag)
                if reply.status_code == 200:
                    try:
                        return Response(200, reply.json(), reply.headers.get("ETag"))
                    except ValueError as error:
                        raise FeedError(f"not JSON: {url}") from error
                problem = f"HTTP {reply.status_code}"
                if reply.status_code not in RETRY_STATUSES:
                    break
                wait = max(wait, _retry_after(reply))
            if attempt < self.retries:
                time.sleep(min(wait, 60))
        raise FeedError(f"{problem}: {url}")


def _retry_after(reply: requests.Response) -> float:
    try:
        return float(reply.headers.get("Retry-After", 0))
    except ValueError:
        return 0.0
