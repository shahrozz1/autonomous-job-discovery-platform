"""Everything that touches the database."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path

from .config import SQL, Board
from .dedupe import Item
from .extract import Facts
from .match import title_key
from .models import Posting


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:32]


class Store:
    def __init__(self, path: Path | str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript((SQL / "schema.sql").read_text(encoding="utf-8"))

    def close(self) -> None:
        self.db.commit()
        self.db.close()

    def rows(self, sql: str, *params) -> list[sqlite3.Row]:
        return self.db.execute(sql, params).fetchall()

    def value(self, sql: str, *params):
        row = self.db.execute(sql, params).fetchone()
        return row[0] if row else None

    # --- boards ---------------------------------------------------------------------------------

    def sync_boards(self, boards: list[Board]) -> None:
        """Make the boards table match config/boards.csv. Dropped boards are kept but inactive."""
        self.db.execute("UPDATE boards SET active = 0")
        self.db.executemany(
            """INSERT INTO boards (platform, board, company) VALUES (?, ?, ?)
               ON CONFLICT (platform, board) DO UPDATE SET company = excluded.company, active = 1""",
            [(b.platform, b.board, b.company) for b in boards],
        )

    def active_boards(self) -> list[sqlite3.Row]:
        return self.rows("SELECT * FROM boards WHERE active = 1 ORDER BY platform, board")

    def known_versions(self) -> dict[tuple[str, str, str], str | None]:
        """Postings already described, and when the company last changed them."""
        return {
            (r["platform"], r["board"], r["source_id"]): r["updated_at"]
            for r in self.rows(
                """SELECT b.platform, b.board, p.source_id, p.updated_at
                   FROM postings AS p JOIN boards AS b USING (board_id)
                   WHERE p.description IS NOT NULL"""
            )
        }

    def board_failed(self, board_id: int) -> None:
        self.db.execute("UPDATE boards SET failures = failures + 1 WHERE board_id = ?", (board_id,))

    def board_read(
        self, board_id: int, today: str, etag: str | None, listed: int | None = None, in_us: int | None = None
    ) -> None:
        """Record a successful read. The counts are left out when the board hadn't changed."""
        self.db.execute(
            """UPDATE boards SET checked_at = ?, failures = 0, etag = ?, listed = COALESCE(?, listed),
                   in_us = COALESCE(?, in_us) WHERE board_id = ?""",
            (today, etag, listed, in_us, board_id),
        )

    # --- postings -------------------------------------------------------------------------------

    def save_posting(self, board_id: int, posting: Posting, family: str, today: str) -> bool:
        """Insert or update a posting. Returns True when it is new."""
        is_new = (
            self.value("SELECT 1 FROM postings WHERE board_id = ? AND source_id = ?", board_id, posting.source_id)
            is None
        )
        # A posting listed without its description hasn't changed, so what is stored stays.
        self.db.execute(
            """INSERT INTO postings (board_id, source_id, title, title_key, family, location,
                   feed_workplace, department, url, posted_at, updated_at, first_seen, last_seen, description,
                   feed_pay_min, feed_pay_max)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (board_id, source_id) DO UPDATE SET
                   title = excluded.title, title_key = excluded.title_key, family = excluded.family,
                   url = excluded.url, last_seen = excluded.last_seen, closed_at = NULL,
                   posted_at = COALESCE(excluded.posted_at, posted_at),
                   location = IIF(excluded.description IS NULL, location, excluded.location),
                   feed_workplace = COALESCE(excluded.feed_workplace, feed_workplace),
                   department = COALESCE(excluded.department, department),
                   updated_at = IIF(excluded.description IS NULL, updated_at, excluded.updated_at),
                   feed_pay_min = IIF(excluded.description IS NULL, feed_pay_min, excluded.feed_pay_min),
                   feed_pay_max = IIF(excluded.description IS NULL, feed_pay_max, excluded.feed_pay_max),
                   description = COALESCE(excluded.description, description)""",
            (
                board_id, posting.source_id, posting.title, title_key(posting.title), family,
                posting.location, posting.workplace, posting.department, posting.url,
                posting.posted_at, posting.updated_at, today, today, posting.description,
                posting.pay_min, posting.pay_max,
            ),
        )  # fmt: skip
        return is_new

    def mark_still_open(self, board_id: int, today: str) -> None:
        """The board hasn't changed, so everything open on it is still open."""
        self.db.execute("UPDATE postings SET last_seen = ? WHERE board_id = ? AND closed_at IS NULL", (today, board_id))

    def close_missing(self, board_id: int, listed_ids: set[str], today: str) -> int:
        """Close this board's postings that are no longer listed. Returns how many."""
        gone = [
            (today, r["posting_id"])
            for r in self.rows(
                "SELECT posting_id, source_id FROM postings WHERE board_id = ? AND closed_at IS NULL", board_id
            )
            if r["source_id"] not in listed_ids
        ]
        self.db.executemany("UPDATE postings SET closed_at = ? WHERE posting_id = ?", gone)
        return len(gone)

    def drop_unmatched(self, keep: set[int]) -> int:
        """Remove open postings that no longer match the profile (after a settings change)."""
        stale = [
            (r["posting_id"],)
            for r in self.rows("SELECT posting_id FROM postings WHERE closed_at IS NULL")
            if r["posting_id"] not in keep
        ]
        self.db.executemany("DELETE FROM postings WHERE posting_id = ?", stale)
        return len(stale)

    def open_postings(self) -> list[sqlite3.Row]:
        return self.rows(
            """SELECT p.*, b.company, b.platform FROM postings AS p JOIN boards AS b USING (board_id)
               WHERE p.closed_at IS NULL AND p.description IS NOT NULL"""
        )

    def dedupe_items(self) -> list[Item]:
        return [
            Item(r["posting_id"], r["company"], r["title"], r["title_key"], r["description"])
            for r in self.rows(
                """SELECT p.posting_id, b.company, p.title, p.title_key, p.description
                   FROM postings AS p JOIN boards AS b USING (board_id)
                   WHERE p.description IS NOT NULL"""
            )
        ]

    def save_roles(self, roles: dict[int, int]) -> None:
        self.db.executemany(
            "UPDATE postings SET role_id = ? WHERE posting_id = ?", [(role, posting) for posting, role in roles.items()]
        )

    def save_facts(
        self, posting_id: int, facts: Facts, markets: tuple[str, ...], points: int, reasons: list[str]
    ) -> None:
        self.db.execute(
            """UPDATE postings SET years_min = ?, pay_min = ?, pay_max = ?, workplace = ?, score = ?, reasons = ?
               WHERE posting_id = ?""",
            (facts.years_min, facts.pay_min, facts.pay_max, facts.workplace, points, json.dumps(reasons), posting_id),
        )
        self.db.execute("DELETE FROM posting_skills WHERE posting_id = ?", (posting_id,))
        self.db.executemany(
            "INSERT INTO posting_skills VALUES (?, ?, ?)",
            [(posting_id, skill, level) for skill, level in facts.skills.items()],
        )
        self.db.execute("DELETE FROM posting_markets WHERE posting_id = ?", (posting_id,))
        self.db.executemany("INSERT INTO posting_markets VALUES (?, ?)", [(posting_id, m) for m in markets])

    # --- answers from the optional AI step --------------------------------------------------------

    def ai_facts(self) -> dict[str, dict]:
        return {r["content_hash"]: json.loads(r["facts"]) for r in self.rows("SELECT * FROM ai_facts")}

    def save_ai_facts(self, text_hash: str, model: str, facts: dict, day: date) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO ai_facts VALUES (?, ?, ?, ?)",
            (text_hash, model, json.dumps(facts), day.isoformat()),
        )
        self.db.commit()  # each answer cost money, so it is saved right away

    # --- search, runs and settings ----------------------------------------------------------------

    def rebuild_search(self) -> None:
        self.db.execute("DELETE FROM search")
        self.db.execute(
            """INSERT INTO search (rowid, title, company, location, description)
               SELECT posting_id, title, company, location, description FROM open_roles"""
        )

    def save_run(self, **fields) -> None:
        names = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        self.db.execute(f"INSERT INTO runs ({names}) VALUES ({marks})", tuple(fields.values()))

    def get_meta(self, key: str) -> str | None:
        return self.value("SELECT value FROM meta WHERE key = ?", key)

    def set_meta(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))
