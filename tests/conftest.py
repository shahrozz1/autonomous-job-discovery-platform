import json
from pathlib import Path

import pytest

from roleful.config import PROFILE, SKILLS
from roleful.extract import SkillRules
from roleful.match import Profile
from roleful.store import Store

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def rules():
    return SkillRules.load(SKILLS)


@pytest.fixture(scope="session")
def profile():
    return Profile.load(PROFILE)


@pytest.fixture
def store():
    store = Store(":memory:")
    yield store
    store.close()


@pytest.fixture
def feed():
    """Load a sample feed. The samples are made up, in the shape each platform really sends."""
    return lambda name: json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
