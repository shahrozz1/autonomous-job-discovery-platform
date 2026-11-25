"""Data quality checks.

Each file in sql/checks returns the rows that break a rule, so a check passes when it returns
nothing. An "error" fails the run; a "warning" is only reported.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import SQL
from .store import Store


@dataclass(frozen=True)
class Check:
    name: str
    severity: str
    rule: str
    rows: list[dict]

    @property
    def passed(self) -> bool:
        return not self.rows


def run_checks(store: Store) -> list[Check]:
    results = []
    for path in sorted((SQL / "checks").glob("*.sql")):
        sql = path.read_text(encoding="utf-8")
        severity = re.search(r"^-- severity: (\w+)", sql, re.M).group(1)
        rule = re.findall(r"^-- (?!severity)(.+)$", sql, re.M)[0]
        rows = [dict(row) for row in store.rows(sql)]
        results.append(Check(path.stem, severity, rule, rows))
    return results
