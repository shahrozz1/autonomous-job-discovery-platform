from datetime import date

import pytest

from roleful.extract import Facts
from roleful.score import score

TODAY = date(2026, 11, 24)
MARKET = ("Dallas",)


def points(profile, facts=None, markets=MARKET, posted="2026-11-24"):
    return score(facts or Facts(), markets, posted, profile, TODAY)


def test_points_add_up_to_100(profile):
    assert sum(profile.points.values()) == 100
    have = dict.fromkeys(profile.candidate["skills"], "required")
    ideal = Facts(skills=have, years_min=1, pay_min=60000, pay_max=80000)
    assert points(profile, ideal)[0] >= 98


def test_the_worst_case_is_low(profile):
    worst = Facts(skills={"Oracle": "required"}, years_min=8, pay_min=30000, pay_max=40000)
    assert points(profile, worst, ("Other US",), "2025-01-01")[0] <= 15


@pytest.mark.parametrize(("easier", "harder"), [(0, 2), (2, 3), (3, 4)])
def test_more_experience_means_fewer_points(profile, easier, harder):
    assert points(profile, Facts(years_min=easier))[0] > points(profile, Facts(years_min=harder))[0]


def test_required_skills_weigh_more_than_nice_to_haves(profile):
    missing_required = Facts(skills={"SQL": "required", "Oracle": "required"})
    missing_preferred = Facts(skills={"SQL": "required", "Oracle": "preferred"})
    assert points(profile, missing_preferred)[0] > points(profile, missing_required)[0]


def test_a_match_on_many_skills_beats_a_match_on_one(profile):
    one = Facts(skills={"SQL": "required"})
    many = Facts(skills=dict.fromkeys(("SQL", "Excel", "Tableau", "Python"), "required"))
    assert points(profile, many)[0] > points(profile, one)[0]


def test_newer_is_better(profile):
    days = ["2026-11-24", "2026-11-18", "2026-11-12", "2026-11-01", "2026-10-01", "2026-06-01"]
    scores = [points(profile, posted=day)[0] for day in days]
    assert scores == sorted(scores, reverse=True)
    assert len(set(scores)) == len(scores)


def test_high_pay_with_no_stated_experience_is_treated_as_senior(profile):
    plain = Facts(pay_min=70000, pay_max=90000)
    senior = Facts(pay_min=190000, pay_max=270000)
    assert points(profile, senior)[0] < points(profile, plain)[0]
    assert "senior" in " ".join(points(profile, senior)[1])


def test_reasons_explain_the_score(profile):
    facts = Facts(skills={"SQL": "required", "Oracle": "required"}, years_min=1)
    assert points(profile, facts)[1] == [
        "Skills: 1 of 2, missing Oracle",
        "Experience: 1+ years",
        "Location: Dallas",
        "Posted today",
        "Pay: not listed",
    ]
