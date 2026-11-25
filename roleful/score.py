"""Score how well a posting fits the profile, from 0 to 100, with the reasons spelled out."""

from __future__ import annotations

from datetime import date

from .extract import REQUIRED, Facts
from .match import Profile


def score(
    facts: Facts, markets: tuple[str, ...], posted_at: str | None, profile: Profile, today: date
) -> tuple[int, list[str]]:
    parts = [
        ("skills", *_skills(facts, profile)),
        ("experience", *_experience(facts, profile)),
        ("location", *_location(markets, profile)),
        ("freshness", *_freshness(posted_at, today)),
        ("pay", *_pay(facts, profile)),
    ]
    total = sum(profile.points[name] * share for name, share, _ in parts)
    return round(total), [reason for _, _, reason in parts]


# What a posting with no listed skills is worth. Every posting also starts with one "imaginary" skill
# at this value, because matching one skill out of one says less than matching six out of six.
_NEUTRAL = 0.6


def _skills(facts: Facts, profile: Profile) -> tuple[float, str]:
    if not facts.skills:
        return _NEUTRAL, "No specific skills listed"
    have = set(profile.candidate["skills"])
    weights = {s: 1.0 if level == REQUIRED else 0.5 for s, level in facts.skills.items()}
    matched = sum(w for s, w in weights.items() if s in have)
    share = (matched + _NEUTRAL) / (sum(weights.values()) + 1)
    missing = sorted(s for s in weights if s not in have)
    text = f"Skills: {len(weights) - len(missing)} of {len(weights)}"
    return share, text + (f", missing {', '.join(missing[:4])}" if missing else "")


def _experience(facts: Facts, profile: Profile) -> tuple[float, str]:
    years, limit = facts.years_min, profile.candidate["max_years"]
    if years is None:
        if facts.pay_min and facts.pay_min >= profile.candidate["senior_pay"]:
            return 0.2, "Experience: not stated, but the pay is senior level"
        return 0.75, "Experience: not stated"
    text = f"Experience: {years}+ years" if years else "Experience: none required"
    over = years - limit
    share = 1.0 if over < 0 else {0: 0.8, 1: 0.35}.get(over, 0.0)
    return share, text


def _location(markets: tuple[str, ...], profile: Profile) -> tuple[float, str]:
    wanted = [m for m in profile.candidate["markets"] if m in markets]
    if wanted:
        return 1.0, f"Location: {', '.join(wanted)}"
    return 0.2, "Location: outside the target markets"


def _freshness(posted_at: str | None, today: date) -> tuple[float, str]:
    if not posted_at:
        return 0.3, "Posting date unknown"
    days = max(0, (today - date.fromisoformat(posted_at)).days)
    steps = ((3, 1.0), (7, 0.85), (14, 0.6), (30, 0.35), (60, 0.1))
    share = next((s for limit, s in steps if days <= limit), 0.0)
    when = "today" if days == 0 else "yesterday" if days == 1 else f"{days} days ago"
    return share, f"Posted {when}"


def _pay(facts: Facts, profile: Profile) -> tuple[float, str]:
    if facts.pay_max is None:
        return 0.4, "Pay: not listed"
    text = f"Pay: ${facts.pay_min / 1000:.0f}K to ${facts.pay_max / 1000:.0f}K"
    return (1.0 if facts.pay_max >= profile.candidate["pay_floor"] else 0.0), text
