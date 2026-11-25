import pytest

from roleful.places import is_vague, locate


@pytest.mark.parametrize(
    ("location", "markets"),
    [
        ("Dallas, TX", ("Dallas",)),
        ("Plano, TX or Remote", ("Dallas", "Remote")),
        ("US-CA-Menlo Park", ("California",)),
        ("San Francisco, CA | New York City, NY", ("California", "New York")),
        ("Massachusetts - Boston", ("Other US",)),
        ("Remote (USA)", ("Remote",)),
        ("Remote", ("Remote",)),
        ("Remote (United States | Canada)", ("Remote",)),
        ("Buffalo, New York", ("Other US",)),
        ("Dublin, CA", ("California",)),
        ("Ontario, California", ("California",)),
        ("New Mexico", ("Other US",)),
        ("Georgia, United States", ("Other US",)),
    ],
)
def test_places_in_the_us(location, markets):
    place = locate(location)
    assert place.in_us
    assert place.markets == markets


@pytest.mark.parametrize(
    "location",
    ["Pune, IN", "Berlin, DE", "Bogota, CO", "Tel Aviv, IL", "Toronto, ON, CA", "Remote - Canada", "London", "Mexico"],
)
def test_places_that_only_look_american(location):
    assert not locate(location).in_us


def test_the_feeds_country_breaks_ties():
    assert locate("HQ", country="US").in_us
    assert not locate("HQ", country="FR").in_us
    assert not locate("HQ").in_us


def test_a_remote_workplace_adds_the_remote_market():
    assert locate("Austin, TX", workplace="remote").markets == ("Remote",)


def test_vague():
    assert is_vague(" Hybrid ")
    assert not is_vague("Hybrid - Chicago")
