import json
from types import SimpleNamespace

import pytest

from classifier import classify_post, parse_classification


def test_parse_classification_extracts_fields():
    raw = json.dumps({"categorie": "produit", "quoi": "3DS craquée", "score": 85})
    result = parse_classification(raw)
    assert result == {"categorie": "produit", "quoi": "3DS craquée", "score": 85}


def test_parse_classification_coerces_score_to_int():
    raw = json.dumps({"categorie": "bruit", "quoi": "n/a", "score": "5"})
    result = parse_classification(raw)
    assert result["score"] == 5
    assert isinstance(result["score"], int)


def test_parse_classification_rejects_invalid_categorie():
    raw = json.dumps({"categorie": "autre_chose", "quoi": "x", "score": 50})
    with pytest.raises(ValueError):
        parse_classification(raw)


class FakeMessages:
    def __init__(self, response_text):
        self.response_text = response_text
        self.last_call_kwargs = None

    def create(self, **kwargs):
        self.last_call_kwargs = kwargs
        content_block = SimpleNamespace(text=self.response_text)
        return SimpleNamespace(content=[content_block])


class FakeClient:
    def __init__(self, response_text):
        self.messages = FakeMessages(response_text)


def test_classify_post_calls_client_and_parses_result():
    raw = json.dumps({"categorie": "prestation", "quoi": "développeur React", "score": 70})
    fake_client = FakeClient(raw)

    result = classify_post("Need a React dev", "Anyone available for a small gig?", client=fake_client)

    assert result == {"categorie": "prestation", "quoi": "développeur React", "score": 70}
    assert "Need a React dev" in fake_client.messages.last_call_kwargs["messages"][0]["content"]
