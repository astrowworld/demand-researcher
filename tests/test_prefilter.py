from prefilter import is_demand_intent


def test_detects_french_cherche():
    assert is_demand_intent("Je cherche une 3DS craquée pas chère")


def test_detects_english_looking_for():
    assert is_demand_intent("Looking for a cracked Switch, any condition")


def test_detects_wtb_shorthand():
    assert is_demand_intent("WTB Nintendo 3DS broken screen ok")


def test_detects_forhire_style_need_a_dev():
    assert is_demand_intent("[HIRING] Need a developer for a React freelance gig")


def test_is_case_insensitive():
    assert is_demand_intent("CHERCHE quelqu'un pour réparer ma console")


def test_rejects_unrelated_post():
    assert not is_demand_intent("Just built my first PC, here's a photo dump")


def test_rejects_empty_text():
    assert not is_demand_intent("")
