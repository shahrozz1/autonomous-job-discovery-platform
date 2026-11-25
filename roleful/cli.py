"""The command line: python -m roleful <command>"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from . import __version__, pipeline, report
from .checks import run_checks
from .config import DATABASE, PROFILE, SITE_DATA, SKILLS
from .evaluate import evaluate
from .extract import SkillRules
from .match import Profile
from .store import Store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="roleful", description="Find entry-level jobs on company career pages.")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--db", type=Path, default=DATABASE, help="database file (default: data/roleful.db)")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("run", help="read every board, then score, group and check what matches")
    commands.add_parser("refresh", help="recompute facts and scores from stored text (no network)")
    commands.add_parser("check", help="run the data quality checks")
    commands.add_parser("report", help="print the SQL analysis as Markdown tables")
    commands.add_parser("evaluate", help="measure how accurate the extraction rules are")

    export = commands.add_parser("export", help="write the dashboard's data files")
    export.add_argument("--out", type=Path, default=SITE_DATA)

    search = commands.add_parser("search", help="search the open jobs")
    search.add_argument("words", nargs="*", help='for example: "demand planning" sql')
    search.add_argument("--market", help="Dallas, New York, Chicago, California, Remote")
    search.add_argument("--max-years", type=int, help="most experience the job may ask for")
    search.add_argument("--min-score", type=int, default=0)
    search.add_argument("--limit", type=int, default=20)

    enrich = commands.add_parser("enrich", help="have Claude read new postings (needs an API key)")
    enrich.add_argument("--limit", type=int, default=25, help="most postings to send in one go")

    args = parser.parse_args(argv)
    store = Store(args.db)
    try:
        return {
            "run": _run,
            "refresh": _refresh,
            "check": _check,
            "report": _report,
            "evaluate": _evaluate,
            "export": _export,
            "search": _search,
            "enrich": _enrich,
        }[args.command](store, args)
    finally:
        store.close()


def _run(store: Store, args) -> int:
    print("Reading boards...")
    s = pipeline.run(store)
    print(
        f"{s.listed:,} postings on {s.boards_read + s.boards_same} boards ({s.boards_same} unchanged, "
        f"{s.boards_failed} failed) in {s.seconds:.0f}s\n"
        f"{s.matched} open matches: {s.new} new, {s.closed} closed since the last run"
    )
    for error in s.errors[:10]:
        print(f"  could not read {error}")
    return _check(store, args)


def _refresh(store: Store, args) -> int:
    pipeline.refresh(store, Profile.load(PROFILE), SkillRules.load(SKILLS), date.today())
    print(f"Rescored {store.value('SELECT COUNT(*) FROM postings WHERE closed_at IS NULL')} open postings")
    return 0


def _check(store: Store, args) -> int:
    failed = False
    for check in run_checks(store):
        mark = "ok  " if check.passed else check.severity.upper()[:4]
        print(f"  {mark} {check.name}: {check.rule}" + ("" if check.passed else f" ({len(check.rows)} rows)"))
        for row in check.rows[:3]:
            print(f"         {row}")
        failed = failed or (not check.passed and check.severity == "error")
    return 1 if failed else 0


def _report(store: Store, args) -> int:
    for result in report.analysis(store).values():
        print(f"\n### {result['question']}\n\n{report.as_markdown(result['rows'])}")
    return 0


def _evaluate(store: Store, args) -> int:
    print("\n".join(evaluate(store)))
    return 0


def _export(store: Store, args) -> int:
    for path in report.export(store, args.out, Profile.load(PROFILE)):
        print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KB)")
    return 0


def _search(store: Store, args) -> int:
    where, params = ["r.score >= ?"], [args.min_score]
    if args.words:
        where.append("r.posting_id IN (SELECT rowid FROM search WHERE search MATCH ?)")
        params.append(" ".join('"' + word.replace('"', "") + '"' for word in args.words))
    if args.market:
        where.append("EXISTS (SELECT 1 FROM posting_markets m WHERE m.posting_id = r.posting_id AND m.market = ?)")
        params.append(args.market)
    if args.max_years is not None:
        where.append("COALESCE(r.years_min, 0) <= ?")
        params.append(args.max_years)
    found = store.rows(
        f"SELECT * FROM open_roles AS r WHERE {' AND '.join(where)} ORDER BY r.score DESC, r.posted_at DESC LIMIT ?",
        *params,
        args.limit,
    )
    for r in found:
        years = {None: "experience not stated", 0: "no experience asked"}.get(
            r["years_min"], f"{r['years_min']}+ years"
        )
        pay = f"${r['pay_min'] / 1000:.0f}K-${r['pay_max'] / 1000:.0f}K" if r["pay_min"] else "pay not listed"
        print(f"{r['score']:>3}  {r['title']} | {r['company']} | {r['location']} | {years} | {pay}\n     {r['url']}")
    print(f"{len(found)} jobs")
    return 0


def _enrich(store: Store, args) -> int:
    try:
        from .enrich import enrich
    except ImportError:
        print('The AI step needs its extra package: pip install -e ".[ai]"', file=sys.stderr)
        return 2
    print(enrich(store, limit=args.limit))
    return 0
