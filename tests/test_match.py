import pytest

from roleful.match import title_key


@pytest.mark.parametrize(
    ("title", "family"),
    [
        ("Data Analyst", "Data and BI"),
        ("Business Intelligence Analyst II", "Data and BI"),
        ("Analyst, Measurement & Insights", "Data and BI"),
        ("Business Operations Analyst", "Business and operations analyst"),
        ("Strategy & Operations Associate (Hybrid)", "Business and operations analyst"),
        ("Demand Planner", "Supply chain and inventory"),
        ("Supply Chain Coordinator", "Supply chain and inventory"),
        ("Assistant Buyer", "Buying, pricing and merchandising"),
        ("Pricing Analyst", "Buying, pricing and merchandising"),
        ("Implementation Specialist", "Operations associate and coordinator"),
        ("Program Coordinator", "Operations associate and coordinator"),
    ],
)
def test_titles_worth_reading(profile, title, family):
    assert profile.family(title) == family


@pytest.mark.parametrize(
    "title",
    [
        "Senior Data Analyst",
        "Data Analyst III",
        "Analytics Manager",
        "Supply Chain Intern",
        "Data Engineer",
        "Tax Analyst",
        "Security Operations Analyst",
        "Recruiting Coordinator",
        "Operations Associate, Dallas, #156",
        "Operations Associate (Full-Time) - Mall of America",
        "Sales Development Associate",
        "Media Buyer",
        "German-speaking Operations Specialist",
        "Account Executive",
    ],
)
def test_titles_to_skip(profile, title):
    assert profile.family(title) is None


def test_title_key_ignores_the_city():
    assert title_key("Operations Coordinator (Legacy West)") == title_key("Operations Coordinator (Soho)")
    assert title_key("Data Analyst - Dallas, TX") == "data analyst"
    assert title_key("Jr. Buyer") == "junior buyer"
    assert title_key("Data Analyst") != title_key("Product Analyst")
