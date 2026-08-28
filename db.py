import sqlite3

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS signaux (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reddit_id TEXT UNIQUE NOT NULL,
    sub TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    permalink TEXT NOT NULL,
    categorie TEXT NOT NULL,
    quoi TEXT NOT NULL,
    score INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def get_conn(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(SCHEMA)
    conn.commit()


def insert_signal(conn: sqlite3.Connection, signal: dict) -> int | None:
    try:
        cur = conn.execute(
            """
            INSERT INTO signaux (reddit_id, sub, title, url, permalink, categorie, quoi, score)
            VALUES (:reddit_id, :sub, :title, :url, :permalink, :categorie, :quoi, :score)
            """,
            signal,
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError as e:
        # Only treat as dedup if it's a UNIQUE constraint on reddit_id
        if "UNIQUE constraint failed" in str(e) and "reddit_id" in str(e):
            return None
        # Re-raise any other IntegrityError (e.g. NOT NULL violations)
        raise


def get_signals(conn: sqlite3.Connection, categorie: str | None = None) -> list[dict]:
    query = "SELECT * FROM signaux"
    params: tuple = ()
    if categorie:
        query += " WHERE categorie = ?"
        params = (categorie,)
    query += " ORDER BY score DESC, created_at DESC"
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]
