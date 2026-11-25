"""Whole runs against made-up boards, with no network."""

from copy import deepcopy
from datetime import date

import pytest

from roleful import pipeline
from roleful.checks import run_checks
from roleful.config import Board
from roleful.http import FeedError, Response

DAY1, DAY2, DAY3 = date(2026, 11, 24), date(2026, 11, 25), date(2026, 11, 27)
LIST = "https://boards-api.greenhouse.io/v1/boards/maplegoods/jobs"
DETAIL = LIST + "/{}?pay_transparency=true"
LEVER = "https://api.lever.co/v0/postings/harborline?mode=json"


class FakeWeb:
    """Stands in for the internet: a dict of address -> JSON, plus a log of what was asked for."""

    def __init__(self, feed):
        detail = feed("greenhouse_detail")
        self.pages = {LIST: feed("greenhouse_list"), LEVER: feed("lever_list")}
        self.pages |= {DETAIL.format(i): detail for i in (101, 102)}
        self.asked = []

    def get_json(self, url, etag=None):
        self.asked.append(url)
        if url not in self.pages:
            raise FeedError(f"HTTP 404: {url}")
        current = str(hash(str(self.pages[url])))
        if etag == current:
            return Response(304, None, etag)
        return Response(200, deepcopy(self.pages[url]), current)


@pytest.fixture
def web(feed, monkeypatch):
    web = FakeWeb(feed)
    monkeypatch.setattr(pipeline, "Client", lambda: web)
    boards = [Board("Maple Goods", "greenhouse", "maplegoods"), Board("Harborline", "lever", "harborline")]
    monkeypatch.setattr(pipeline, "load_boards", lambda path: boards)
    return web


def run(store, day):
    return pipeline.run(store, today=day, say=lambda text: None)


def titles(store):
    return sorted(r["title"] for r in store.rows("SELECT title FROM postings WHERE closed_at IS NULL"))


def test_first_run_keeps_only_what_matches(store, web):
    summary = run(store, DAY1)
    # the senior job and the London job are left out; "Hybrid" turns out to be Dallas
    assert titles(store) == ["Business Analyst", "Operations Coordinator", "Supply Chain Analyst"]
    assert (summary.boards_read, summary.listed, summary.matched, summary.new) == (2, 5, 3, 3)
    assert summary.details == 2


def test_facts_are_worked_out(store, web):
    run(store, DAY1)
    row = store.rows("SELECT * FROM postings WHERE title = 'Supply Chain Analyst'")[0]
    skills = {r["skill"]: r["level"] for r in store.rows(
        "SELECT * FROM posting_skills WHERE posting_id = ?", row["posting_id"]
    )}  # fmt: skip
    assert skills == {"Excel": "required", "SQL": "required", "Forecasting": "required", "Tableau": "preferred"}
    assert (row["years_min"], row["pay_min"], row["pay_max"]) == (1, 64480, 74880)
    assert row["score"] >= 90


def test_nothing_is_downloaded_twice(store, web):
    run(store, DAY1)
    web.asked.clear()
    summary = run(store, DAY2)
    assert (summary.boards_same, summary.boards_read, summary.details) == (2, 0, 0)
    assert web.asked == [LIST, LEVER] or web.asked == [LEVER, LIST]
    assert len(titles(store)) == 3
    assert store.value("SELECT MIN(last_seen) FROM postings") == DAY2.isoformat()


def test_only_the_changed_posting_is_fetched_again(store, web):
    run(store, DAY1)
    web.pages[LIST]["jobs"][1]["updated_at"] = "2026-11-25T08:00:00-05:00"
    assert run(store, DAY2).details == 1


def test_a_removed_posting_is_closed_and_can_reopen(store, web):
    run(store, DAY1)
    removed = web.pages[LIST]["jobs"].pop(0)
    assert run(store, DAY2).closed == 1
    assert store.value("SELECT closed_at FROM postings WHERE title = 'Supply Chain Analyst'") == DAY2.isoformat()
    assert store.value("SELECT COUNT(*) FROM open_roles") == 2

    web.pages[LIST]["jobs"].insert(0, removed)
    summary = run(store, DAY3)
    assert (summary.new, summary.closed) == (0, 0)
    assert store.value("SELECT closed_at FROM postings WHERE title = 'Supply Chain Analyst'") is None
    assert store.value("SELECT first_seen FROM postings WHERE title = 'Supply Chain Analyst'") == DAY1.isoformat()


def test_a_board_that_fails_closes_nothing(store, web):
    run(store, DAY1)
    del web.pages[LEVER]
    summary = run(store, DAY2)
    assert (summary.boards_failed, summary.closed) == (1, 0)
    assert "Operations Coordinator" in titles(store)
    assert store.value("SELECT failures FROM boards WHERE company = 'Harborline'") == 1


def test_one_missing_description_does_not_lose_the_board(store, web):
    saved = web.pages.pop(DETAIL.format(102))
    summary = run(store, DAY1)
    assert (summary.boards_failed, summary.new) == (0, 2)
    web.pages[DETAIL.format(102)] = saved
    assert run(store, DAY2).new == 1  # the board is read again even though its list hasn't changed


def test_a_big_board_that_is_suddenly_empty_closes_nothing(store, web):
    extra = [{**web.pages[LIST]["jobs"][2], "id": 900 + i} for i in range(20)]
    web.pages[LIST]["jobs"] += extra
    run(store, DAY1)
    web.pages[LIST]["jobs"] = []
    assert run(store, DAY2).closed == 0
    assert "Supply Chain Analyst" in titles(store)


def test_new_settings_read_every_board_in_full(store, web, monkeypatch):
    run(store, DAY1)
    monkeypatch.setattr(pipeline, "settings_fingerprint", lambda: "changed")
    assert run(store, DAY2).boards_read == 2


def test_search_finds_words_in_the_description(store, web):
    run(store, DAY1)
    found = store.rows("SELECT title FROM search WHERE search MATCH 'logistics'")
    assert [r["title"] for r in found] == ["Operations Coordinator"]


def test_the_data_passes_its_own_checks(store, web):
    run(store, DAY1)
    assert [c.name for c in run_checks(store) if not c.passed] == []


def test_checks_catch_bad_data(store, web):
    run(store, DAY1)
    store.db.execute("UPDATE postings SET pay_min = 224640, pay_max = 143000 WHERE title = 'Business Analyst'")
    store.db.execute("UPDATE postings SET years_min = 100 WHERE title = 'Operations Coordinator'")
    failed = {c.name for c in run_checks(store) if not c.passed}
    assert failed == {"03_unlikely_pay", "04_unlikely_experience"}
