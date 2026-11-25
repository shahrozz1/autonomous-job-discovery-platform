import pytest

from roleful import cli
from roleful.store import Store
from tests.test_pipeline import DAY1, run, web  # noqa: F401


@pytest.fixture
def database(tmp_path, web):  # noqa: F811
    path = tmp_path / "test.db"
    store = Store(path)
    run(store, DAY1)
    store.close()
    return str(path)


def test_search(database, capsys):
    assert cli.main(["--db", database, "search", "reorder points", "--market", "Dallas"]) == 0
    out = capsys.readouterr().out
    assert "Supply Chain Analyst | Maple Goods | Dallas, TX | 1+ years | $64K-$75K" in out
    assert "Operations Coordinator" not in out


def test_search_by_experience(database, capsys):
    cli.main(["--db", database, "search", "--max-years", "1"])
    assert "Operations Coordinator" not in capsys.readouterr().out


def test_check_passes(database, capsys):
    assert cli.main(["--db", database, "check"]) == 0


def test_report_prints_tables(database, capsys):
    assert cli.main(["--db", database, "report"]) == 0
    assert "| skill | roles |" in capsys.readouterr().out


def test_export(database, tmp_path, capsys):
    assert cli.main(["--db", database, "export", "--out", str(tmp_path / "out")]) == 0
    assert (tmp_path / "out" / "roles.json").exists()


def test_refresh_needs_no_network(database, capsys):
    assert cli.main(["--db", database, "refresh"]) == 0
    assert "Rescored 3" in capsys.readouterr().out
