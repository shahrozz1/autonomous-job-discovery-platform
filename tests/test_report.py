import json

from roleful import report
from tests.test_pipeline import DAY1, run, web  # noqa: F401


def test_every_analysis_query_runs_and_asks_a_question(store, web):  # noqa: F811
    run(store, DAY1)
    results = report.analysis(store)
    assert len(results) >= 10
    assert all(result["question"] for result in results.values())
    demand = {r["skill"]: r["roles"] for r in results["skill_demand"]["rows"]}
    assert demand["SQL"] == 2


def test_analysis_runs_on_an_empty_database(store):
    assert report.analysis(store)["skill_demand"]["rows"] == []


def test_export_holds_facts_but_no_descriptions(store, web, profile, tmp_path):  # noqa: F811
    run(store, DAY1)
    for path in report.export(store, tmp_path, profile):
        assert "Maple Goods sells kitchen tools" not in path.read_text(encoding="utf-8")
    roles = json.loads((tmp_path / "roles.json").read_text(encoding="utf-8"))
    assert len(roles) == 3
    assert roles == sorted(roles, key=lambda r: -r["score"])
    summary = json.loads((tmp_path / "insights.json").read_text(encoding="utf-8"))["summary"]
    assert (summary["boards"], summary["listed"], summary["roles"]) == (2, 5, 3)


def test_markdown_table():
    assert report.as_markdown([{"a": 1, "b": None}]) == "| a | b |\n|---|---|\n| 1 |  |"
    assert report.as_markdown([]) == "_No rows yet._"
