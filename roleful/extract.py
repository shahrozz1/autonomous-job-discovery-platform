"""Pull facts out of a posting's text with plain rules.

Every rule works on one line at a time and knows which part of the posting the line is in, so
"401(k) match" is not a salary, "20 years in business" is not a requirement, and a skill under
"Nice to have" is not counted as required.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED, PREFERRED = "required", "preferred"

# Headings, checked in this order. The first pattern that fits names the section.
_SECTIONS = [
    ("preferred", r"prefer|nice.to.have|would be nice|bonus (point|qualif|skill)|^bonus|\bplus(es)?\b|even better|extra credit|good to have|stand out|desired|ideally|great to have|not required"),
    ("about you", r"about you|who you are|ideal candidate|you should have|what we require|what you need"),
    ("boilerplate", r"benefit|perks?\b|compensation|pay (range|transparen)|salary|we offer|equal|eeo|itar|e-verify|privacy|scam|accommodat|agenc|fair chance|disclaimer|about us|who we are|our (values|mission|culture|commitment|story)|\bwhy\b|how we work|notice|physical|work environment|application|interview|referral|hiring range|self-identification|total rewards|^about (?!the (role|job|position|team)|this)"),
    ("requirements", r"qualif|require|you('|’)?(ll|re| will)? (bring|need|have)|must.have|looking for|skills|experience|minimum|background|what it takes|(good|great) fit|be a fit|might thrive|we('|’)re excited about you|education|success in this role|credentials"),
    ("duties", r"responsib|what you|you will|you('|’)ll|in this role|the role|about the|about this|role|day.to.day|duties|impact|opportunity|overview|job|position|purpose|contribut"),
]  # fmt: skip
_SECTIONS = [(name, re.compile(pattern, re.I)) for name, pattern in _SECTIONS]
_SOFT = re.compile(r"\b(preferred|preferably|a plus|nice to have|bonus|ideally|desirable|advantageous)\b", re.I)


@dataclass
class Facts:
    skills: dict[str, str] = field(default_factory=dict)  # skill -> "required" or "preferred"
    years_min: int | None = None
    pay_min: float | None = None
    pay_max: float | None = None
    workplace: str | None = None


class SkillRules:
    """The skill patterns in config/skills.toml, compiled once."""

    def __init__(self, entries: list[dict]):
        self._rules = [
            (
                entry["name"],
                [re.compile(p, re.I) for p in entry.get("match", [])]
                + [re.compile(p) for p in entry.get("match_case", [])],
                [re.compile(p) for p in entry.get("except", [])],
            )
            for entry in entries
        ]
        self.names = [name for name, _, _ in self._rules]

    @classmethod
    def load(cls, path: Path) -> SkillRules:
        return cls(tomllib.loads(path.read_text(encoding="utf-8"))["skill"])

    def in_line(self, line: str) -> set[str]:
        found = set()
        for name, patterns, exceptions in self._rules:
            blocked = [m.span() for pattern in exceptions for m in pattern.finditer(line)]
            for pattern in patterns:
                if any(not _inside(m.span(), blocked) for m in pattern.finditer(line)):
                    found.add(name)
                    break
        return found


def _inside(span: tuple[int, int], blocked: list[tuple[int, int]]) -> bool:
    return any(start <= span[0] and span[1] <= end for start, end in blocked)


def section_lines(text: str) -> list[tuple[str, str]]:
    """Each line of the posting with the section it belongs to."""
    out = []
    section = "intro"
    for line in text.split("\n"):
        if line.startswith("# "):
            heading = line[2:]
            section = next((name for name, p in _SECTIONS if p.search(heading)), "other")
            section = "requirements" if section == "about you" else section
            out.append((section, heading))
        elif line.strip():
            out.append((section, line))
    return out


def extract(text: str, company: str, rules: SkillRules) -> Facts:
    lines = section_lines(text)
    return Facts(
        skills=_skills(lines, company, rules),
        years_min=_years(lines),
        workplace=_workplace(text),
        **dict(zip(("pay_min", "pay_max"), _pay(lines), strict=True)),
    )


# --- skills -------------------------------------------------------------------------------------


def _skills(lines, company: str, rules: SkillRules) -> dict[str, str]:
    skills: dict[str, str] = {}
    for section, line in lines:
        if section == "boilerplate":
            continue
        level = PREFERRED if section == "preferred" or _SOFT.search(line) else REQUIRED
        for name in rules.in_line(line):
            if name.lower() in company.lower():
                continue  # Snowflake mentioning Snowflake is not a skill requirement
            if skills.get(name) != REQUIRED:
                skills[name] = level
    return skills


# --- years of experience --------------------------------------------------------------------------

_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_NUM = r"(\d{1,2}|" + "|".join(_WORDS) + ")"
_YEARS = re.compile(
    rf"\b{_NUM}\s*(?:\(\d{{1,2}}\)\s*)?\+?\s*(?:(?:-|–|—|to|or)\s*{_NUM}\s*\+?\s*)?"
    r"(?:or more |plus |full )?(?:years?|yrs?)\b",
    re.I,
)
_NOT_EXPERIENCE_BEFORE = re.compile(
    r"(past|last|next|previous|first|over the|within|every|each|for (over|more than|nearly)|founded|than)\s*(the )?$",
    re.I,
)
_NOT_EXPERIENCE_AFTER = re.compile(
    r"^['’]?s?\s*(old|of age|ago|contract|commitment|of service|vest|in business|in a row|running|rotation|term\b|program|anniversary)",
    re.I,
)
_OFF_TOPIC = re.compile(r"licen[sc]e|driving record|over year|year[- ]end|anniversary", re.I)
_EARLY = re.compile(
    r"\b(new grad(uate)?s?|recent(ly)? grad\w*|early[- ]career|entry[- ]level|"
    r"no (prior )?experience (is )?(required|necessary)|graduates?\b.{0,20}\b20\d\d)\b",
    re.I,
)
_DEGREE_OR = re.compile(
    r"(degree|diploma|ged|bachelor\S*|associate\S*|b\.?[as]\.?)\b[^.]{0,60}\bor\s+(at least |a minimum of )?$", re.I
)
_OR_DEGREE = re.compile(r"^[^.;]*\bor (an? )?(bachelor|degree|b\.?[as]\.?\b|associate)(?!.*\d\+? years)", re.I)
_YEARS_FIRST = re.compile(r"^- (minimum( of)? |at least |approximately |roughly |~)?\S{1,9}( to \S+)? years?\b", re.I)
_UP_TO = re.compile(r"(up to|less than|under|fewer than|no more than|maximum of)\s*$", re.I)
_OPTIONAL_BEFORE = re.compile(r"\b(preferred|preferably|ideally|nice to have|bonus|a plus)\b[^.;]{0,30}$", re.I)
_OPTIONAL_AFTER = re.compile(r"\b(preferred|a plus|desired|nice to have|bonus|advantageous)\s*\)?$", re.I)


def _years(lines) -> int | None:
    """The fewest years of experience that would meet the posting's requirements.

    Several lines can each set a bar, so the highest one counts. Within a line, "or" means either
    amount is enough, so the lowest one counts.
    """
    bars: dict[str, list[int]] = {"requirements": [], "elsewhere": []}
    early = False
    for section, line in lines:
        if section in {"boilerplate", "preferred"}:
            continue
        early = early or bool(_EARLY.search(line))
        bar = _line_years(line, strict=section != "requirements")
        if bar is not None:
            bars["requirements" if section == "requirements" else "elsewhere"].append(bar)
    asked = bars["requirements"] or bars["elsewhere"]
    if asked:
        return max(asked)
    return 0 if early else None


def _line_years(line: str, strict: bool) -> int | None:
    """Years asked for in one line.

    Outside the requirements section the line has to say "experience" or open with the number, since
    "five years" can be about anything there.
    """
    if _OFF_TOPIC.search(line):
        return None
    if strict and not (re.search(r"experience", line, re.I) or _YEARS_FIRST.search(line)):
        return None
    bar, previous_end = None, 0
    for m in _YEARS.finditer(line):
        before, after = line[: m.start()], line[m.end() :]
        clause = re.split(r"[,.;]", after, maxsplit=1)[0].strip()
        if (
            _NOT_EXPERIENCE_BEFORE.search(before)
            or _NOT_EXPERIENCE_AFTER.search(after)
            or _OPTIONAL_BEFORE.search(before)
            or _OPTIONAL_AFTER.search(clause)
        ):
            continue
        low = m.group(1).lower()
        value = _WORDS[low] if low in _WORDS else int(low)
        if value > 20:
            continue
        first = bar is None
        either = _DEGREE_OR.search(before) or _OR_DEGREE.search(after)
        if _UP_TO.search(before) or (first and (either or _EARLY.search(before))):
            value = 0  # "a degree or 2+ years": with the degree, no experience is asked for
        if first:
            bar = value
        elif re.search(r"\bor\b", line[previous_end : m.start()], re.I):
            bar = min(bar, value)
        else:
            bar = max(bar, value)
        previous_end = m.end()
    return bar


# --- pay ----------------------------------------------------------------------------------------

_AMOUNT = r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s?([kK])?\b"
_UNIT = r"(?:\s*(?:usd|per (?:year|hour|annum)|/ ?(?:yr|year|hr|hour)|annually|an hour|hourly))*"
_RANGE = re.compile(rf"\$\s?{_AMOUNT}{_UNIT}\s*(?:-|–|—|to|and)\s*(?:usd\s*)?\$?\s?{_AMOUNT}", re.I)
_ONE_RATE = re.compile(rf"\$\s?{_AMOUNT}\s*(?:usd\s*)?(?:/ ?|per |an )(?:hr|hour)\b", re.I)
_ONE_SALARY = re.compile(
    rf"\b(?:salary|base pay|pay rate|hourly rate|compensation for this)\b[^$\n]{{0,60}}\$\s?{_AMOUNT}", re.I
)
_PAY_WORDS = re.compile(r"salary|base|\bpay\b|compensation|range|hourly|per hour|annual|wage|/ ?yr|/ ?hr|level", re.I)
_NOT_PAY = re.compile(
    r"401|stipend|reimburs|revenue|raised|funding|valuation|budget\b|billion|million|savings|wellness|"
    r"per diem|referral|month\b|sign-?on",
    re.I,
)


def _pay(lines) -> tuple[float | None, float | None]:
    """The first believable pay range, as yearly dollars.

    When a posting lists several ranges (by level or by city) the first one is used.
    """
    fallback: tuple[float | None, float | None] = (None, None)
    for _, line in lines:
        if "$" not in line:
            continue
        for pay, span in _line_pay(line):
            nearby = line[max(0, span[0] - 60) : span[1] + 30]
            if _NOT_PAY.search(nearby):
                continue
            if _PAY_WORDS.search(line):
                return pay
            if fallback[0] is None:
                fallback = pay
    return fallback


def _line_pay(line: str):
    """Every believable amount in a line: ranges first, then single rates and salaries."""
    for m in _RANGE.finditer(line):
        low = _yearly(m.group(1), m.group(2) or m.group(4), line)
        high = _yearly(m.group(3), m.group(4) or m.group(2), line)
        if low and high and low <= high:
            yield (low, high), m.span()
    for pattern in (_ONE_RATE, _ONE_SALARY):
        for m in pattern.finditer(line):
            rate = _yearly(m.group(1), m.group(2), line)
            if rate:
                yield (rate, rate), m.span()


def _yearly(number: str, k: str | None, line: str) -> float | None:
    value = float(number.replace(",", ""))
    if k:
        value *= 1000
    return yearly(value, monthly=bool(re.search(r"per month|monthly|/ ?mo\b", line, re.I)))


def yearly(value: float, monthly: bool = False) -> float | None:
    """A believable yearly salary, or None. Small numbers are hourly rates (2,080 hours a year)."""
    if value < 200:
        value *= 2080
    elif monthly and value < 20_000:
        value *= 12
    return round(value) if 24_000 <= value <= 500_000 else None


def yearly_range(low: float, high: float) -> tuple[float | None, float | None]:
    """A pay range typed in by a company. Real feeds include slips like "$108 to $143,000"."""
    low, high = yearly(low), yearly(high)
    return (low, high) if low and high and low <= high else (None, None)


# --- workplace ------------------------------------------------------------------------------------


def _workplace(text: str) -> str | None:
    if re.search(r"\bhybrid\b", text, re.I):
        return "hybrid"
    if re.search(
        r"\b(fully|100%|this is a) remote\b|\bremote (role|position|opportunity)\b|work from anywhere", text, re.I
    ):
        return "remote"
    if re.search(r"\b(on-?site|in[- ]office|in[- ]person)\b", text, re.I):
        return "onsite"
    return None
