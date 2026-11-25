import pytest

from roleful.extract import extract, section_lines


def facts(text, rules, company="Acme"):
    return extract(text, company, rules)


# --- skills ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "- Strong Excel skills",
        "- Proficiency in Microsoft excel",
        "- Advanced excel (pivot tables, lookups)",
        "- Tools: Word, Excel, PowerPoint",
        "- Experience in Excel as well as SQL",
        "- Ability to use excel at a high level",
        "- SQL, excel, and a BI tool",
        "- EXCEL modeling",
    ],
)
def test_excel_the_software(rules, line):
    assert "Excel" in facts(f"# Requirements\n{line}", rules).skills


@pytest.mark.parametrize(
    "line",
    [
        "- You will excel in a fast-paced team",
        "- Excel at structuring ambiguous problems",
        "- Excel in a collaborative environment",
        "- Ability to work and excel within a dynamic team",
        "- The tools and opportunity to excel.",
        "- People who excel here are curious",
    ],
)
def test_excel_the_verb(rules, line):
    assert "Excel" not in facts(f"# Requirements\n{line}", rules).skills


@pytest.mark.parametrize(
    ("line", "found"),
    [
        ("- Python, R, or SQL", True),
        ("- Experience with R programming", True),
        ("- Work with the R&D team using Python", False),
        ("- Report to Sam R. Jones", False),
    ],
)
def test_r_the_language(rules, line, found):
    assert ("R" in facts(f"# Requirements\n{line}", rules).skills) is found


def test_nice_to_haves_are_preferred_and_benefits_are_ignored(rules):
    text = "# Requirements\n- SQL\n- Tableau is a plus\n# Nice to have\n- Python\n# Benefits\n- Excel training budget"
    assert facts(text, rules).skills == {"SQL": "required", "Tableau": "preferred", "Python": "preferred"}


def test_required_wins_when_a_skill_is_listed_twice(rules):
    text = "# Nice to have\n- SQL\n# Requirements\n- SQL"
    assert facts(text, rules).skills == {"SQL": "required"}


def test_a_companys_own_product_is_not_a_skill(rules):
    text = "# Requirements\n- Work on Snowflake with SQL"
    assert set(facts(text, rules, company="Snowflake").skills) == {"SQL"}
    assert set(facts(text, rules).skills) == {"SQL", "Snowflake"}


def test_ai_tools_means_using_ai_not_selling_it(rules):
    assert "AI tools" in facts("# Requirements\n- Comfortable using AI tools like ChatGPT", rules).skills
    assert "AI tools" not in facts("# The role\nOur AI agents answer customer calls.", rules).skills


# --- years of experience --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "years"),
    [
        ("2+ years of experience in analytics", 2),
        ("3 - 5 years of relevant experience", 3),
        ("1–3 years in operations", 1),
        ("Minimum of one (1) year of experience", 1),
        ("At least two years' experience with SQL", 2),
        ("0-2 years of work experience", 0),
        ("Up to 2 years of experience", 0),
        ("~5 years of experience in sales operations", 5),
        # the longest requirement in the line is the bar...
        ("3-5 years of experience in analytics, with at least 2 years in a startup", 3),
        # ...unless either one will do
        ("Bachelor's degree and 1+ years of experience; OR 4+ years of experience", 1),
        ("Bachelor's degree or 3+ years of experience in purchasing", 0),
        ("Bachelor's degree; or 4+ years of professional experience", 0),
        ("2+ years of experience in manufacturing OR a bachelor's degree", 0),
        ("High school diploma, GED equivalent or 1-2 years related experience", 0),
        ("MS plus 2 years, or BS or BA plus 3 years, of full-time experience", 2),
        # a preference about the details doesn't make the years optional
        ("2+ years of experience in operations, ideally in market data", 2),
        ("1-2 years of customer-facing experience in preferably a startup", 1),
        # but a preference about the years does
        ("2+ years of analytical experience preferred", None),
        ("Preferably 3+ years of experience", None),
        # not about experience at all
        ("Valid license with no suspensions in the past 3 years", None),
        ("We have been in business for over 20 years", None),
        ("Must be 18 years of age", None),
        ("Within your first year of employment", None),
    ],
)
def test_years(rules, line, years):
    assert facts(f"# Requirements\n- {line}", rules).years_min == years


def test_the_highest_bar_counts_across_lines(rules):
    text = "# Requirements\n- 1+ years with Tableau\n- 4+ years of experience in analytics"
    assert facts(text, rules).years_min == 4


def test_preferred_years_do_not_count(rules):
    text = "# Requirements\n- 1+ years of experience\n# Preferred qualifications\n- 6+ years of experience"
    assert facts(text, rules).years_min == 1


def test_new_grads_need_no_experience(rules):
    assert facts("# About you\n- Recent graduates welcome", rules).years_min == 0
    assert facts("# About you\n- Curious", rules).years_min is None


# --- pay ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "pay"),
    [
        ("The base salary range is $65,000 - $80,000 per year", (65000, 80000)),
        ("Salary: $60-75k", (60000, 75000)),
        ("Pay: $80,000-90,000 + bonus", (80000, 90000)),
        ("$37/hr - $45/hr", (76960, 93600)),
        ("Level 1: $22.00 - $25.00", (45760, 52000)),
        ("The hourly rate is $30.00 per hour", (62400, 62400)),
        ("The salary for this role is $88,837", (88837, 88837)),
        ("The budgeted annual salary range is $75,000 to $100,000.", (75000, 100000)),
        ("We raised $20 to $30 million", (None, None)),
        ("401(k) match from $2,000 to $4,000", (None, None)),
        ("Home office stipend of $500 to $1,000", (None, None)),
        ("Customers save $50,000 - $90,000 in revenue", (None, None)),
    ],
)
def test_pay(rules, line, pay):
    found = facts(f"# Compensation\n{line}", rules)
    assert (found.pay_min, found.pay_max) == pay


def test_the_first_pay_range_is_used(rules):
    text = "# Pay range\nLevel 1: $85,000 - $100,000\nLevel 2: $100,000 - $130,000"
    assert facts(text, rules).pay_max == 100000


# --- sections and workplace ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("heading", "section"),
    [
        ("Basic qualifications", "requirements"),
        ("Who you are", "requirements"),
        ("You might thrive in this role if you", "requirements"),
        ("Preferred skills and experience", "preferred"),
        ("Bonus points", "preferred"),
        ("What you'll do", "duties"),
        ("About the role", "duties"),
        ("About Maple Goods", "boilerplate"),
        ("Compensation and benefits", "boilerplate"),
        ("Equal opportunity", "boilerplate"),
    ],
)
def test_headings(heading, section):
    assert section_lines(f"# {heading}\ntext")[1] == (section, "text")


@pytest.mark.parametrize(
    ("text", "workplace"),
    [
        ("This is a hybrid role", "hybrid"),
        ("This is a fully remote position", "remote"),
        ("Work in-person at our HQ", "onsite"),
        ("Great team", None),
    ],
)
def test_workplace(rules, text, workplace):
    assert facts(text, rules).workplace == workplace
