"""How good are the extraction rules? Three checks anyone can rerun.

1. Years of experience against tests/data/years_labels.csv: 200 randomly chosen postings, each read
   and labeled with the least experience that would meet its requirements.
2. Pay read from the text against the pay companies entered as data in their feeds.
3. The Excel rule against the one this project started with, which counted the word "excel" anywhere
   and so counted the verb too.
"""

from __future__ import annotations

import csv
import re

from .config import ROOT, SKILLS
from .extract import SkillRules, extract
from .store import Store

LABELS = ROOT / "tests" / "data" / "years_labels.csv"


def evaluate(store: Store) -> list[str]:
    rules = SkillRules.load(SKILLS)
    rows = store.rows("SELECT p.*, b.company, b.platform, b.board FROM postings p JOIN boards b USING (board_id)")
    facts = {
        (r["platform"], r["board"], r["source_id"]): (r, extract(r["description"], r["company"], rules)) for r in rows
    }
    return [_years(facts), _pay(facts), _excel(facts)]


def _years(facts) -> str:
    with LABELS.open(newline="", encoding="utf-8") as file:
        labels = list(csv.DictReader(file))
    checked, misses = 0, []
    for label in labels:
        found = facts.get((label["platform"], label["board"], label["source_id"]))
        if not found:
            continue  # taken down before this database first saw it
        checked += 1
        wanted = int(label["years"]) if label["years"] else None
        if found[1].years_min != wanted:
            misses.append(f"{label['company']}, {label['title']}: {found[1].years_min} instead of {wanted}")
    text = f"Years of experience: {checked - len(misses)} of {checked} labeled postings right"
    return text + "".join(f"\n  miss: {miss}" for miss in misses)


def _pay(facts) -> str:
    both = same = 0
    for row, found in facts.values():
        if row["feed_pay_min"] is not None and found.pay_min is not None:
            both += 1
            same += abs(row["feed_pay_min"] - found.pay_min) < 1500 and abs(row["feed_pay_max"] - found.pay_max) < 1500
    return f"Pay: the text rule gives the same range as the feed on {same} of {both} postings that have both"


def _excel(facts) -> str:
    before = [found for row, found in facts.values() if re.search(r"\bexcel\b", row["description"], re.I)]
    after = [found for found in before if "Excel" in found.skills]
    dropped = len(before) - len(after)
    return (
        f"Excel: the old rule matched {len(before)} postings, the new one {len(after)}; "
        f"{dropped} of the old matches were not the software as a job skill"
    )
