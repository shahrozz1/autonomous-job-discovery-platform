"""Run the SQL analysis and write the files the dashboard reads.

Only facts are exported (title, company, place, pay, skills, link). Descriptions belong to the
companies that wrote them, so they stay in the local database.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import SQL
from .match import Profile
from .store import Store


def analysis(store: Store) -> dict[str, dict]:
    """Every query in sql/analysis, by file name, with the question it answers."""
    out = {}
    for path in sorted((SQL / "analysis").glob("*.sql")):
        sql = path.read_text(encoding="utf-8")
        lines = []
        for line in sql.splitlines():
            if not line.startswith("--"):
                break
            lines.append(line.removeprefix("--").strip())
        rows = [dict(row) for row in store.rows(sql)]
        out[path.stem[3:]] = {"question": " ".join(lines), "sql": path.name, "rows": rows}
    return out


def roles(store: Store) -> list[dict]:
    """One entry per open role, with every place it is listed."""
    skills: dict[int, list] = {}
    for row in store.rows("SELECT * FROM posting_skills ORDER BY level DESC, skill"):
        skills.setdefault(row["posting_id"], []).append([row["skill"], row["level"] == "required"])
    places: dict[int, set] = {}
    markets: dict[int, set] = {}
    for row in store.rows(
        """SELECT p.role_id, p.location, m.market FROM postings AS p
           JOIN posting_markets AS m USING (posting_id) WHERE p.closed_at IS NULL"""
    ):
        places.setdefault(row["role_id"], set()).add(row["location"])
        markets.setdefault(row["role_id"], set()).add(row["market"])
    return [
        {
            "id": r["role_id"],
            "title": r["title"],
            "company": r["company"],
            "family": r["family"],
            "locations": sorted(places[r["role_id"]]),
            "markets": sorted(markets[r["role_id"]]),
            "workplace": r["workplace"],
            "posted": r["posted_at"],
            "firstSeen": r["first_seen"],
            "years": r["years_min"],
            "pay": [r["pay_min"], r["pay_max"]] if r["pay_min"] is not None else None,
            "skills": skills.get(r["posting_id"], []),
            "score": r["score"],
            "reasons": json.loads(r["reasons"]),
            "listings": r["listings"],
            "url": r["url"],
        }
        for r in store.rows("SELECT * FROM open_roles ORDER BY score DESC, posted_at DESC, title")
    ]


def summary(store: Store) -> dict:
    run = store.rows("SELECT * FROM runs ORDER BY run_id DESC LIMIT 1")
    run = dict(run[0]) if run else {}
    return {
        "generated": datetime.now().isoformat(timespec="minutes"),
        "runDate": run.get("run_date"),
        "boards": store.value("SELECT COUNT(*) FROM boards WHERE active = 1"),
        "companies": store.value("SELECT COUNT(DISTINCT LOWER(company)) FROM boards WHERE active = 1"),
        "listed": run.get("listed"),
        "inUs": run.get("in_us"),
        "postings": store.value("SELECT COUNT(*) FROM postings WHERE closed_at IS NULL"),
        "roles": store.value("SELECT COUNT(*) FROM open_roles"),
        "entry": store.value("SELECT COUNT(*) FROM open_roles WHERE years_min <= 2"),
        "strong": store.value("SELECT COUNT(*) FROM open_roles WHERE score >= 80"),
        "newThisWeek": store.value(
            "SELECT COUNT(*) FROM open_roles WHERE posted_at >= DATE((SELECT MAX(run_date) FROM runs), '-7 days')"
        ),
    }


def export(store: Store, folder: Path, profile: Profile) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    profile_facts = {
        "skills": profile.candidate["skills"],
        "maxYears": profile.candidate["max_years"],
        "markets": profile.candidate["markets"],
        "points": profile.points,
    }
    files = {
        "roles.json": roles(store),
        "insights.json": {"summary": summary(store), "profile": profile_facts, "analysis": analysis(store)},
    }
    for name, data in files.items():
        (folder / name).write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return [folder / name for name in files]


def as_markdown(rows: list[dict]) -> str:
    """A query result as a Markdown table."""
    if not rows:
        return "_No rows yet._"
    head = list(rows[0])
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    lines += ["| " + " | ".join("" if v is None else str(v) for v in row.values()) + " |" for row in rows]
    return "\n".join(lines)
