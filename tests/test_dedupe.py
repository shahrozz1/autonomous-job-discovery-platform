from roleful.dedupe import Item, group, phrases, similarity

BASE = "Run daily shipments for the store and keep the stock room counts right every single week. " * 4
OTHER = "Build dashboards in SQL and present pricing results to the leadership team each month. " * 4


def item(posting_id, title, text, company="Acme", key="operations coordinator"):
    return Item(posting_id, company, title, key, text)


def test_same_job_in_two_cities_is_one_role():
    items = [item(1, "Operations Coordinator", BASE + "Dallas"), item(2, "Operations Coordinator", BASE + "Chicago")]
    assert group(items) == {1: 1, 2: 1}


def test_same_title_but_different_work_stays_apart():
    assert group([item(1, "Coordinator", BASE), item(2, "Coordinator", OTHER)]) == {1: 1, 2: 2}


def test_different_companies_are_never_grouped():
    assert group([item(1, "Coordinator", BASE), item(2, "Coordinator", BASE, company="Other")]) == {1: 1, 2: 2}


def test_different_full_titles_need_nearly_identical_text():
    # about 80% alike: enough for identical titles, not enough when only the core title matches
    changed = BASE.replace("stock room", "sales floor", 1)
    share = similarity(phrases(BASE), phrases(changed))
    assert 0.7 <= share < 0.9
    assert group([item(1, "Coordinator", BASE), item(2, "Coordinator", changed)]) == {1: 1, 2: 1}
    assert group([item(1, "Coordinator (East)", BASE), item(2, "Coordinator (West)", changed)]) == {1: 1, 2: 2}


def test_chains_join_into_one_group():
    items = [item(i, "Coordinator", BASE + extra) for i, extra in ((3, "a b"), (1, "c d"), (2, "e f"))]
    assert set(group(items).values()) == {1}


def test_empty_descriptions_match_nothing():
    assert similarity(set(), phrases(BASE)) == 0.0
