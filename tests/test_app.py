import pytest

from app import create_app
from db import get_conn, init_db, insert_signal


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = get_conn(db_path)
    init_db(conn)
    insert_signal(conn, {
        "reddit_id": "p1",
        "sub": "hardwareswap",
        "title": "ISO cracked 3DS",
        "url": "https://reddit.com/r/hardwareswap/comments/p1",
        "permalink": "https://reddit.com/r/hardwareswap/comments/p1",
        "categorie": "produit",
        "quoi": "3DS craquée",
        "score": 80,
    })
    insert_signal(conn, {
        "reddit_id": "p2",
        "sub": "forhire",
        "title": "Need a React dev",
        "url": "https://reddit.com/r/forhire/comments/p2",
        "permalink": "https://reddit.com/r/forhire/comments/p2",
        "categorie": "prestation",
        "quoi": "développeur React",
        "score": 70,
    })
    conn.close()

    app = create_app(db_path=db_path)
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_index_lists_all_signals(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"3DS craqu\xc3\xa9e" in response.data
    assert b"d\xc3\xa9veloppeur React" in response.data


def test_index_filters_by_categorie(client):
    response = client.get("/?categorie=produit")
    assert b"3DS craqu\xc3\xa9e" in response.data
    assert b"d\xc3\xa9veloppeur React" not in response.data


def test_index_works_on_first_run_before_any_signal_exists(tmp_path):
    db_path = str(tmp_path / "fresh.db")

    app = create_app(db_path=db_path)
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        response = test_client.get("/")

    assert response.status_code == 200
