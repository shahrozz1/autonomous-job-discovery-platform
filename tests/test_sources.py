from roleful.sources import Ashby, Greenhouse, Lever


def test_greenhouse_list_has_no_descriptions(feed):
    posting = Greenhouse().parse_list(feed("greenhouse_list"), "maplegoods", "Maple Goods")[0]
    assert (posting.title, posting.location, posting.posted_at) == ("Supply Chain Analyst", "Dallas, TX", "2026-11-20")
    assert posting.description is None
    assert Greenhouse().detail_url(posting).endswith("/maplegoods/jobs/101?pay_transparency=true")


def test_greenhouse_detail_fills_in_text_and_first_pay_range(feed):
    posting = Greenhouse().parse_list(feed("greenhouse_list"), "maplegoods", "Maple Goods")[0]
    Greenhouse().parse_detail(feed("greenhouse_detail"), posting)
    assert "# Requirements\n- 1-3 years of experience" in posting.description
    assert posting.department == "Operations"
    assert (posting.pay_min, posting.pay_max) == (64480, 74880)  # $31 to $36 an hour, 2,080 hours


def test_greenhouse_uses_the_office_when_the_location_is_not_a_place(feed):
    posting = Greenhouse().parse_list(feed("greenhouse_list"), "maplegoods", "Maple Goods")[1]
    assert posting.location == "Hybrid"
    Greenhouse().parse_detail(feed("greenhouse_detail"), posting)
    assert posting.location == "Dallas, Texas, United States"


def test_greenhouse_ignores_a_mistyped_pay_range(feed):
    payload = feed("greenhouse_detail")
    payload["pay_input_ranges"] = [{"min_cents": 10800, "max_cents": 14300000, "currency_type": "USD"}]
    posting = Greenhouse().parse_list(feed("greenhouse_list"), "maplegoods", "Maple Goods")[0]
    Greenhouse().parse_detail(payload, posting)
    assert (posting.pay_min, posting.pay_max) == (None, None)


def test_lever(feed):
    posting = Lever().parse_list(feed("lever_list"), "harborline", "Harborline")[0]
    assert posting.location == "Chicago, IL; Remote"
    assert (posting.workplace, posting.posted_at) == ("onsite", "2026-11-25")
    assert (posting.pay_min, posting.pay_max) == (52000, 62400)
    assert "# What you need\n- 2+ years of experience in logistics" in posting.description
    assert Lever().detail_url(posting) is None


def test_ashby_skips_unlisted_jobs_and_reads_pay(feed):
    postings = Ashby().parse_list(feed("ashby_list"), "fernwood", "Fernwood")
    assert len(postings) == 1
    posting = postings[0]
    assert posting.location == "New York, NY; San Francisco, CA"
    assert (posting.country, posting.workplace) == ("United States", "hybrid")
    assert (posting.pay_min, posting.pay_max) == (70000, 85000)
    assert posting.description == "# You have\n- 1+ years of experience with SQL"
