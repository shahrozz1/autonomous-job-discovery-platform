"""Work out where a job is from the location text a company typed in.

There is no standard format. Real feeds say "New York, NY", "US-CA-Menlo Park", "Massachusetts -
Boston", "Pune, IN" (India, not Indiana) and "Remote (USA)", so each piece is checked in order of
how sure the clue is: a named US state or country first, then known foreign places, then two-letter
state codes, then city names on their own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
}  # fmt: skip
_US_CITIES = (
    "new york|nyc|manhattan|brooklyn|san francisco|\\bsf\\b|bay area|los angeles|san diego|san jose|"
    "oakland|palo alto|mountain view|menlo park|redwood city|sunnyvale|santa monica|santa clara|"
    "san mateo|foster city|irvine|culver city|chicago|dallas|fort worth|plano|frisco|irving|austin|"
    "houston|san antonio|boston|seattle|bellevue|kirkland|denver|boulder|atlanta|miami|tampa|orlando|"
    "philadelphia|pittsburgh|phoenix|scottsdale|tempe|nashville|salt lake city|lehi|minneapolis|"
    "detroit|charlotte|raleigh|durham|las vegas|columbus|cincinnati|cleveland|indianapolis|"
    "kansas city|st\\.? louis|baltimore|washington,? d\\.?c|portland|sacramento|milwaukee|jersey city"
)
_FOREIGN = (
    "canada|toronto|vancouver|montreal|ottawa|calgary|waterloo|ontario|quebec|british columbia|"
    "mexico|cdmx|brazil|brasil|s[aã]o paulo|argentina|buenos aires|colombia|bogot[aá]|chile|peru|"
    "costa rica|latam|latin america|united kingdom|england|scotland|\\buk\\b|\\bgb\\b|london|"
    "manchester|ireland|dublin|france|paris|germany|deutschland|berlin|munich|hamburg|spain|madrid|"
    "barcelona|portugal|lisbon|porto|italy|milan|netherlands|amsterdam|belgium|brussels|switzerland|"
    "zurich|austria|vienna|sweden|stockholm|norway|oslo|denmark|copenhagen|finland|helsinki|poland|"
    "warsaw|krakow|czech|prague|romania|bucharest|hungary|budapest|greece|athens|turkey|istanbul|"
    "ukraine|serbia|belgrade|bulgaria|croatia|estonia|lithuania|emea|europe|israel|tel aviv|tlv|"
    "dubai|uae|united arab emirates|saudi|egypt|nigeria|lagos|kenya|nairobi|south africa|india|"
    "bengaluru|bangalore|mumbai|hyderabad|pune|noida|gurugram|gurgaon|chennai|delhi|pakistan|"
    "singapore|malaysia|kuala lumpur|thailand|bangkok|vietnam|hanoi|ho chi minh|philippines|manila|"
    "indonesia|jakarta|china|shanghai|beijing|shenzhen|hong kong|taiwan|taipei|japan|tokyo|korea|"
    "seoul|australia|sydney|melbourne|brisbane|new zealand|auckland|apac|anz\\b"
)
_US_WORDS = r"united states|\busa\b|\bu\.s\.a?\.?|\bus\b|\bamer\b|americas"
_REMOTE = r"remote|distributed|anywhere|work from home|virtual|telecommut"

_MARKETS = {
    "Dallas": (
        r"dallas|fort worth|\bdfw\b|plano|frisco|irving|richardson|addison, t|arlington, t|mckinney|"
        r"allen, t|coppell|grand prairie|southlake|westlake, t|roanoke, t|flower mound|carrollton, t|"
        r"garland, t|mesquite, t|lewisville, t|grapevine, t|farmers branch|lancaster, t|haslet"
    ),
    "New York": r"new york(?! state)|nyc|manhattan|brooklyn|long island city|jersey city|hoboken|secaucus",
    "Chicago": r"chicago|evanston|oak brook|rosemont|deerfield, il|schaumburg|naperville|bolingbrook",
    "California": (
        r"california|,\s*ca\b|us-ca|\bsf\b|san francisco|bay area|los angeles|san diego|san jose|"
        r"oakland|palo alto|mountain view|menlo park|redwood city|sunnyvale|santa monica|santa clara|"
        r"san mateo|foster city|irvine|culver city|beverly hills|long beach|el segundo|burbank"
    ),
}
_UPSTATE = r"buffalo|rochester|albany|syracuse|ithaca|tonawanda"
_VAGUE = {"", "hybrid", "remote", "in-office", "distributed", "n/a", "onsite", "on-site", "office"}


@dataclass(frozen=True)
class Place:
    in_us: bool
    markets: tuple[str, ...] = field(default=())


def is_vague(location: str) -> bool:
    """True when the text names no actual place, such as "Hybrid"."""
    return location.strip().lower() in _VAGUE


def locate(location: str, country: str | None = None, workplace: str | None = None) -> Place:
    home = _country(country)
    markets: list[str] = []
    in_us = False
    pieces = [p.strip() for p in re.split(r"[;|•/]| or (?=[A-Z])", location) if p.strip()] or [""]
    for piece in pieces:
        verdict = _piece_is_us(piece)
        if verdict is None:  # the text gives no clue, so fall back on the feed's country field
            verdict = home if home is not None else _is_remote(piece)
        if not verdict:
            continue
        in_us = True
        for market, pattern in _MARKETS.items():
            if market == "New York" and re.search(_UPSTATE, piece, re.I):
                continue
            if re.search(pattern, piece, re.I):
                markets.append(market)
        if _is_remote(piece):
            markets.append("Remote")
    if in_us and workplace == "remote":
        markets.append("Remote")
    if in_us and not markets:
        markets.append("Other US")
    return Place(in_us, tuple(dict.fromkeys(markets)))


def _is_remote(text: str) -> bool:
    return bool(re.search(_REMOTE, text, re.I))


def _country(country: str | None) -> bool | None:
    if not country:
        return None
    return country.strip().lower() in {"us", "usa", "united states", "united states of america"}


def _piece_is_us(piece: str) -> bool | None:
    """True, False, or None when there is nothing to go on."""
    low = piece.lower()
    if re.search(r"new mexico", low):
        return True
    if re.search(_US_WORDS, low):
        return True
    foreign = re.search(_FOREIGN, low)
    named_state = re.search("|".join(rf"\b{name}\b" for name in _STATES.values()), piece)
    if named_state and not (foreign and foreign.group() not in {"ontario", "dublin", "paris", "london"}):
        return True
    if foreign and not re.search(r"\b(dublin|ontario), (ca|oh)\b", low):
        return False
    if re.search(rf"(?:,\s*|-)({'|'.join(_STATES)})\b", piece):
        return True
    if re.search(_US_CITIES, low):
        return True
    return None
