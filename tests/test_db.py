import sqlite3
import pytest

from db import get_conn, init_db, insert_signal, get_signals


@pytest.fixture
def conn():
    c = get_conn(":memory:")
    init_db(c)
    yield c
    c.close()


def make_signal(**overrides):
    base = {
        "reddit_id": "abc123",
        "sub": "hardwareswap",
        "title": "ISO cracked 3DS",
        "url": "https://reddit.com/r/hardwareswap/comments/abc123",
        "permalink": "https://reddit.com/r/hardwareswap/comments/abc123",
        "categorie": "produit",
        "quoi": "3DS craquée",
        "score": 80,
    }
    base.update(overrides)
    return base


def test_insert_and_fetch_signal(conn):
    row_id = insert_signal(conn, make_signal())
    assert row_id is not None

    rows = get_signals(conn)
    assert len(rows) == 1
    assert rows[0]["quoi"] == "3DS craquée"
    assert rows[0]["categorie"] == "produit"


def test_insert_is_deduplicated_by_reddit_id(conn):
    insert_signal(conn, make_signal())
    second = insert_signal(conn, make_signal(title="duplicate post"))
    assert second is None
    assert len(get_signals(conn)) == 1


def test_get_signals_filters_by_categorie(conn):
    insert_signal(conn, make_signal(reddit_id="p1", categorie="produit"))
    insert_signal(conn, make_signal(reddit_id="p2", categorie="prestation", quoi="dev React"))

    produits = get_signals(conn, categorie="produit")
    assert len(produits) == 1
    assert produits[0]["categorie"] == "produit"


def test_get_signals_orders_by_score_desc(conn):
    insert_signal(conn, make_signal(reddit_id="low", score=10))
    insert_signal(conn, make_signal(reddit_id="high", score=90))

    rows = get_signals(conn)
    assert [r["reddit_id"] for r in rows] == ["high", "low"]


def test_stores_bruit_with_zero_score(conn):
    """Never discard low-score posts — bruit signals with score=0 are valid."""
    row_id = insert_signal(
        conn,
        make_signal(reddit_id="noise1", categorie="bruit", quoi="low quality post", score=0)
    )
    assert row_id is not None

    rows = get_signals(conn, categorie="bruit")
    assert len(rows) == 1
    assert rows[0]["categorie"] == "bruit"
    assert rows[0]["score"] == 0
    assert rows[0]["quoi"] == "low quality post"
