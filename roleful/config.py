"""Where everything lives, and how to load it."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARDS = ROOT / "config" / "boards.csv"
PROFILE = ROOT / "config" / "profile.toml"
SKILLS = ROOT / "config" / "skills.toml"
SQL = ROOT / "sql"
SITE_DATA = ROOT / "site" / "data"
DATABASE = ROOT / "data" / "roleful.db"


@dataclass(frozen=True)
class Board:
    company: str
    platform: str
    board: str


def load_boards(path: Path = BOARDS) -> list[Board]:
    with path.open(newline="", encoding="utf-8") as file:
        return [Board(r["company"], r["platform"], r["board"]) for r in csv.DictReader(file)]
