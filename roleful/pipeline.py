"""One full run: read every board, keep what matches, work out the facts, score and group it.

Downloads happen in three threads, one per platform, so no platform sees two requests at once. All
database work stays on the main thread.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime

from . import dedupe
from .config import BOARDS, PROFILE, SKILLS, Board, load_boards
from .extract import Facts, SkillRules, extract, yearly_range
from .http import Client, FeedError
from .match import Profile
from .models import Posting
from .places import is_vague, locate
from .score import score
from .sources import SOURCES
from .store import Store, content_hash


@dataclass
class BoardResult:
    board_id: int
    status: str  # "read", "same" (unchanged since last run) or "failed"
    etag: str | None = None
    ids: set[str] = field(default_factory=set)
    in_us: int = 0
    matches: list[tuple[Posting, str]] = field(default_factory=list)  # posting, family
    details: int = 0
    error: str = ""


@dataclass
class Summary:
    boards_read: int = 0
    boards_same: int = 0
    boards_failed: int = 0
    listed: int = 0
    in_us: int = 0
    matched: int = 0
    new: int = 0
    closed: int = 0
    details: int = 0
    seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


def run(store: Store, today: date | None = None, say: Callable[[str], None] = print) -> Summary:
    started, clock = datetime.now(), time.monotonic()
    today = today or started.date()
    profile, rules = Profile.load(PROFILE), SkillRules.load(SKILLS)
    store.sync_boards(load_boards(BOARDS))

    settings = settings_fingerprint()
    fresh = store.get_meta("settings") != settings  # new rules: read every board in full
    summary = Summary()
    for result in crawl(store, profile, full=fresh, say=say):
        _record(store, result, today.isoformat(), summary)
    store.set_meta("settings", settings)

    refresh(store, profile, rules, today)
    summary.listed = store.value("SELECT SUM(listed) FROM boards WHERE active = 1") or 0
    summary.in_us = store.value("SELECT SUM(in_us) FROM boards WHERE active = 1") or 0
    summary.matched = store.value("SELECT COUNT(*) FROM postings WHERE closed_at IS NULL")
    summary.seconds = round(time.monotonic() - clock, 1)
    fields = {k: v for k, v in vars(summary).items() if k != "errors"}
    store.save_run(run_date=today.isoformat(), started_at=started.isoformat(timespec="seconds"), **fields)
    store.db.commit()
    return summary


def settings_fingerprint() -> str:
    """Changes whenever the title rules or the board list change."""
    return hashlib.sha256(PROFILE.read_bytes() + BOARDS.read_bytes()).hexdigest()[:16]


# --- reading boards -------------------------------------------------------------------------------


def crawl(store: Store, profile: Profile, full: bool, say: Callable[[str], None]) -> list[BoardResult]:
    known = store.known_versions()
    by_platform: dict[str, list] = {}
    for row in store.active_boards():
        by_platform.setdefault(row["platform"], []).append(row)

    def read_platform(rows) -> list[BoardResult]:
        client = Client()
        return [read_board(client, row, profile, known, full) for row in rows]

    results: list[BoardResult] = []
    with ThreadPoolExecutor(max_workers=len(by_platform) or 1) as pool:
        for platform, batch in zip(by_platform, pool.map(read_platform, by_platform.values()), strict=True):
            say(f"  {platform}: {len(batch)} boards")
            results += batch
    return results


def read_board(client: Client, row, profile: Profile, known: dict, full: bool) -> BoardResult:
    board = Board(row["company"], row["platform"], row["board"])
    source = SOURCES[board.platform]
    result = BoardResult(row["board_id"], "read")
    try:
        reply = client.get_json(source.list_url(board.board), etag=None if full else row["etag"])
        result.etag = reply.etag
        if reply.data is None:
            result.status = "same"
            return result
        for posting in source.parse_list(reply.data, board.board, board.company):
            result.ids.add(posting.source_id)
            place = locate(posting.location, posting.country, posting.workplace)
            result.in_us += place.in_us
            family = profile.family(posting.title)
            if not family or not (place.in_us or is_vague(posting.location)):
                continue
            unchanged = posting.key in known and known[posting.key] == posting.updated_at
            detail = source.detail_url(posting)
            if detail and not unchanged:
                try:
                    source.parse_detail(client.get_json(detail).data, posting)
                except FeedError:  # often taken down seconds ago; forget the ETag so next run looks again
                    result.etag = None
                    continue
                result.details += 1
                if not locate(posting.location, posting.country, posting.workplace).in_us:
                    continue
            result.matches.append((posting, family))
    except (FeedError, KeyError, TypeError, ValueError) as error:
        result.status, result.error = "failed", f"{board.company} ({board.platform}): {error}"
    return result


def _record(store: Store, result: BoardResult, today: str, summary: Summary) -> None:
    summary.details += result.details
    if result.status == "failed":
        summary.boards_failed += 1
        summary.errors.append(result.error)
        store.board_failed(result.board_id)
        return
    if result.status == "same":
        summary.boards_same += 1
        store.board_read(result.board_id, today, result.etag)
        store.mark_still_open(result.board_id, today)
        return
    summary.boards_read += 1
    before = store.value("SELECT listed FROM boards WHERE board_id = ?", result.board_id)
    store.board_read(result.board_id, today, result.etag, len(result.ids), result.in_us)
    for posting, family in result.matches:
        summary.new += store.save_posting(result.board_id, posting, family, today)
    if before and before >= 20 and not result.ids:
        return  # a big board that is suddenly empty is more likely a glitch than a hiring freeze
    summary.closed += store.close_missing(result.board_id, result.ids, today)


# --- facts, scores and groups ---------------------------------------------------------------------


def refresh(store: Store, profile: Profile, rules: SkillRules, today: date) -> None:
    """Work everything out again from the stored text. Needs no network, takes a few seconds."""
    keep = set()
    ai = store.ai_facts()
    for row in store.open_postings():
        if not profile.family(row["title"]):
            continue
        facts = extract(row["description"], row["company"], rules)
        use_feed_values(facts, row)
        fill_gaps(facts, ai.get(content_hash(row["description"])))
        markets = locate(row["location"], None, facts.workplace).markets or ("Other US",)
        points, reasons = score(facts, markets, row["posted_at"], profile, today)
        store.save_facts(row["posting_id"], facts, markets, points, reasons)
        keep.add(row["posting_id"])
    store.drop_unmatched(keep)
    store.save_roles(dedupe.group(store.dedupe_items()))
    store.rebuild_search()
    store.db.commit()


def use_feed_values(facts: Facts, row) -> None:
    """What a company entered as data beats what the rules read from its text."""
    if row["feed_pay_min"] is not None:
        facts.pay_min, facts.pay_max = row["feed_pay_min"], row["feed_pay_max"]
    facts.workplace = row["feed_workplace"] or facts.workplace


def fill_gaps(facts: Facts, ai: dict | None) -> None:
    """Use the AI step's answer only where the rules and the feed found nothing."""
    if not ai:
        return
    if facts.years_min is None and ai["years_min"] is not None and 0 <= ai["years_min"] <= 20:
        facts.years_min = ai["years_min"]
    if facts.pay_min is None and ai["pay_min"] and ai["pay_max"]:
        facts.pay_min, facts.pay_max = yearly_range(ai["pay_min"], ai["pay_max"])
