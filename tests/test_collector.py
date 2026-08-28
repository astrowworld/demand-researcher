from types import SimpleNamespace

from collector import process_submission


def make_submission(**overrides):
    base = dict(
        id="xyz789",
        title="Cherche une 3DS craquée",
        selftext="Peu importe l'état, je répare moi-même",
        url="https://reddit.com/r/hardwareswap/comments/xyz789",
        permalink="/r/hardwareswap/comments/xyz789/cherche_une_3ds",
        subreddit=SimpleNamespace(display_name="hardwareswap"),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_process_submission_stores_signal_when_demand_detected():
    submission = make_submission()
    stored = []

    def fake_classify(title, body):
        return {"categorie": "produit", "quoi": "3DS craquée", "score": 90}

    def fake_store(signal):
        stored.append(signal)
        return 1

    result = process_submission(submission, classify_fn=fake_classify, store_fn=fake_store)

    assert result is not None
    assert result["categorie"] == "produit"
    assert result["reddit_id"] == "xyz789"
    assert result["sub"] == "hardwareswap"
    assert result["permalink"] == "https://reddit.com/r/hardwareswap/comments/xyz789/cherche_une_3ds"
    assert stored == [result]


def test_process_submission_skips_non_demand_post():
    submission = make_submission(title="Just built my first PC", selftext="Photo dump inside")
    calls = []

    def fake_classify(title, body):
        calls.append((title, body))
        return {"categorie": "produit", "quoi": "x", "score": 10}

    def fake_store(signal):
        raise AssertionError("store should not be called for non-demand posts")

    result = process_submission(submission, classify_fn=fake_classify, store_fn=fake_store)

    assert result is None
    assert calls == []  # classifier never invoked — pre-filter saved the LLM call
