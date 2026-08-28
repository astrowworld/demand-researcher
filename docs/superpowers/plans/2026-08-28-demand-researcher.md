# Demand Researcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal tool that streams Reddit in real time, detects posts expressing a demand ("je cherche X"), classifies them as `produit` / `prestation` / `bruit` via Claude Haiku, and shows them in a local dashboard.

**Architecture:** A regex pre-filter runs on every submission from a Reddit firehose (`r/all`) plus two targeted subs (`r/forhire`, `r/slavelabour`); only posts that pass the filter are sent to Claude Haiku for classification; results land in SQLite; a small Flask app renders them sorted/filterable.

**Tech Stack:** Python 3.11+, PRAW (Reddit API), `anthropic` SDK (Claude Haiku `claude-haiku-4-5-20251001`), SQLite (stdlib `sqlite3`), Flask, pytest.

## Global Constraints

- Non-commercial personal use only — no multi-user, no auth (per spec's Non-objectifs).
- Reddit API: read-only, OAuth via PRAW, must stay under 100 req/min (spec §1).
- No historical search — streaming only, from time of launch forward (spec §1, Non-objectifs).
- All classified posts stored, including `bruit`/low score — never discard post-classification (spec §3).
- No push notifications in V1 — dashboard only (spec Non-objectifs).
- Secrets (Reddit + Anthropic credentials) via environment variables only, never hardcoded (per user's global security rules).

---

## File Structure

```
demand-researcher/
├── .env.example
├── requirements.txt
├── config.py            # constants: DB path, targeted subs, regex keywords, model name
├── db.py                 # SQLite schema + insert/query
├── prefilter.py           # regex demand-intent detection
├── classifier.py          # Claude Haiku call + JSON parsing
├── reddit_client.py       # PRAW instance + submission stream generator
├── collector.py            # orchestration: process_submission + run_collector
├── app.py                  # Flask dashboard
├── templates/
│   └── index.html
├── run_collector.py         # entrypoint script for the collector loop
├── CLAUDE.md
├── README.md
└── tests/
    ├── test_db.py
    ├── test_prefilter.py
    ├── test_classifier.py
    ├── test_collector.py
    └── test_app.py
```

---

### Task 1: Config + SQLite storage layer

**Files:**
- Create: `config.py`
- Create: `db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `config.DB_PATH: str`, `config.TARGETED_SUBS: list[str]`, `config.CLAUDE_MODEL: str`
- Produces: `db.get_conn(path: str | None = None) -> sqlite3.Connection`
- Produces: `db.init_db(conn: sqlite3.Connection) -> None`
- Produces: `db.insert_signal(conn: sqlite3.Connection, signal: dict) -> int | None` — `signal` keys: `reddit_id, sub, title, url, permalink, categorie, quoi, score`. Returns the new row id, or `None` if `reddit_id` already existed (dedup).
- Produces: `db.get_signals(conn: sqlite3.Connection, categorie: str | None = None) -> list[dict]` — ordered by `score DESC, created_at DESC`.

- [ ] **Step 1: Write `config.py`**

```python
import os

DB_PATH = os.environ.get("DEMAND_RESEARCHER_DB", "demand_researcher.db")
TARGETED_SUBS = ["forhire", "slavelabour"]
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

DEMAND_KEYWORDS = [
    r"\bcherche\b",
    r"\brecherch(e|es|ons)\b",
    r"\bISO\b",
    r"\bWTB\b",
    r"looking for",
    r"where (can|do) i (find|buy)",
    r"need a (dev|developer|freelance|freelancer)",
    r"anyone (know|selling)",
    r"want to buy",
    r"\bà la recherche\b",
    r"quelqu'un (a|aurait)",
]
```

- [ ] **Step 2: Write the failing test for the DB layer**

```python
# tests/test_db.py
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd ~/projects/demand-researcher && python -m pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'db'` (module doesn't exist yet).

- [ ] **Step 4: Write minimal implementation**

```python
# db.py
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
    except sqlite3.IntegrityError:
        return None


def get_signals(conn: sqlite3.Connection, categorie: str | None = None) -> list[dict]:
    query = "SELECT * FROM signaux"
    params: tuple = ()
    if categorie:
        query += " WHERE categorie = ?"
        params = (categorie,)
    query += " ORDER BY score DESC, created_at DESC"
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/projects/demand-researcher && python -m pytest tests/test_db.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
cd ~/projects/demand-researcher
git add config.py db.py tests/test_db.py
git commit -m "feat: add config and SQLite storage layer"
```

---

### Task 2: Regex demand-intent pre-filter

**Files:**
- Create: `prefilter.py`
- Test: `tests/test_prefilter.py`

**Interfaces:**
- Consumes: `config.DEMAND_KEYWORDS: list[str]` (Task 1)
- Produces: `prefilter.is_demand_intent(text: str) -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_prefilter.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/projects/demand-researcher && python -m pytest tests/test_prefilter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prefilter'`

- [ ] **Step 3: Write minimal implementation**

```python
# prefilter.py
import re

import config

_COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in config.DEMAND_KEYWORDS]


def is_demand_intent(text: str) -> bool:
    if not text:
        return False
    return any(pattern.search(text) for pattern in _COMPILED_PATTERNS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/projects/demand-researcher && python -m pytest tests/test_prefilter.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/projects/demand-researcher
git add prefilter.py tests/test_prefilter.py
git commit -m "feat: add regex demand-intent pre-filter"
```

---

### Task 3: Claude Haiku classifier

**Files:**
- Create: `classifier.py`
- Test: `tests/test_classifier.py`

**Interfaces:**
- Consumes: `config.CLAUDE_MODEL: str` (Task 1)
- Produces: `classifier.classify_post(title: str, body: str, client=None) -> dict` — returns `{"categorie": str, "quoi": str, "score": int}`. `categorie` is one of `"produit"`, `"prestation"`, `"bruit"`.
- Produces: `classifier.parse_classification(raw_text: str) -> dict` (pure parsing, used internally and directly testable)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_classifier.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/projects/demand-researcher && python -m pytest tests/test_classifier.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'classifier'`

- [ ] **Step 3: Write minimal implementation**

```python
# classifier.py
import json

import anthropic

import config

VALID_CATEGORIES = {"produit", "prestation", "bruit"}

SYSTEM_PROMPT = (
    "Tu classes un post Reddit pour savoir s'il exprime une demande "
    "exploitable. Réponds UNIQUEMENT avec un JSON de la forme "
    '{"categorie": "produit"|"prestation"|"bruit", "quoi": "description courte", '
    '"score": 0-100}. "produit" = quelqu\'un cherche un produit physique à '
    "acheter. \"prestation\" = quelqu'un cherche un service/freelance/développeur. "
    "\"bruit\" = ce n'est pas une vraie demande (annonce, discussion générale, etc.)."
)


def parse_classification(raw_text: str) -> dict:
    data = json.loads(raw_text)
    categorie = data["categorie"]
    if categorie not in VALID_CATEGORIES:
        raise ValueError(f"Unknown categorie: {categorie!r}")
    return {
        "categorie": categorie,
        "quoi": data["quoi"],
        "score": int(data["score"]),
    }


def classify_post(title: str, body: str, client=None) -> dict:
    if client is None:
        client = anthropic.Anthropic()

    user_content = f"Titre: {title}\nTexte: {body or '(vide)'}"
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    raw_text = response.content[0].text
    return parse_classification(raw_text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/projects/demand-researcher && python -m pytest tests/test_classifier.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/projects/demand-researcher
git add classifier.py tests/test_classifier.py
git commit -m "feat: add Claude Haiku classifier"
```

---

### Task 4: Reddit client wrapper

**Files:**
- Create: `reddit_client.py`
- Test: none (thin wrapper over PRAW network calls — verified manually in Task 7, per the project's I/O-boundary convention: pure logic gets unit tests, live network wrappers get a documented manual check)

**Interfaces:**
- Produces: `reddit_client.get_reddit_instance() -> praw.Reddit` — read-only, credentials from env vars `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`.
- Produces: `reddit_client.stream_submissions(reddit: praw.Reddit, subreddit_name: str)` — generator yielding `praw.models.Submission` objects, `skip_existing=True`.

- [ ] **Step 1: Write `reddit_client.py`**

```python
# reddit_client.py
import os

import praw


def get_reddit_instance() -> praw.Reddit:
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "demand-researcher/0.1 (personal script)"),
    )


def stream_submissions(reddit: praw.Reddit, subreddit_name: str):
    subreddit = reddit.subreddit(subreddit_name)
    yield from subreddit.stream.submissions(skip_existing=True)
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `cd ~/projects/demand-researcher && python -c "import reddit_client"`
Expected: no output, exit code 0 (module has no side effects at import time — `get_reddit_instance()` only reads env vars when called, not on import).

- [ ] **Step 3: Commit**

```bash
cd ~/projects/demand-researcher
git add reddit_client.py
git commit -m "feat: add Reddit client wrapper over PRAW"
```

---

### Task 5: Collector orchestration

**Files:**
- Create: `collector.py`
- Test: `tests/test_collector.py`

**Interfaces:**
- Consumes: `prefilter.is_demand_intent(text: str) -> bool` (Task 2), `classifier.classify_post(title, body, client=None) -> dict` (Task 3), `db.insert_signal(conn, signal: dict) -> int | None` (Task 1), `reddit_client.stream_submissions(reddit, subreddit_name)` (Task 4), `reddit_client.get_reddit_instance()` (Task 4)
- Produces: `collector.process_submission(submission, classify_fn, store_fn) -> dict | None` — `submission` is any object with `.id`, `.title`, `.selftext`, `.url`, `.permalink`, `.subreddit.display_name`. Returns the stored signal dict, or `None` if the pre-filter rejected the post.
- Produces: `collector.watch_stream(subreddit_name: str, reddit, conn) -> None` — infinite loop, calls `process_submission` for every item from `reddit_client.stream_submissions`, catching and logging exceptions per-item so one bad post never kills the loop.
- Produces: `collector.run_collector() -> None` — spawns one thread per source (`"all"` + each of `config.TARGETED_SUBS`), joins them.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_collector.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/projects/demand-researcher && python -m pytest tests/test_collector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collector'`

- [ ] **Step 3: Write minimal implementation**

```python
# collector.py
import logging
import threading

import config
import db
import prefilter
import reddit_client
from classifier import classify_post

logger = logging.getLogger(__name__)


def process_submission(submission, classify_fn=classify_post, store_fn=None) -> dict | None:
    text = f"{submission.title}\n{submission.selftext or ''}"
    if not prefilter.is_demand_intent(text):
        return None

    result = classify_fn(submission.title, submission.selftext)
    signal = {
        "reddit_id": submission.id,
        "sub": submission.subreddit.display_name,
        "title": submission.title,
        "url": submission.url,
        "permalink": f"https://reddit.com{submission.permalink}"
        if not str(submission.permalink).startswith("http")
        else submission.permalink,
        "categorie": result["categorie"],
        "quoi": result["quoi"],
        "score": result["score"],
    }
    if store_fn is not None:
        store_fn(signal)
    return signal


def watch_stream(subreddit_name: str, reddit, conn) -> None:
    for submission in reddit_client.stream_submissions(reddit, subreddit_name):
        try:
            process_submission(
                submission,
                store_fn=lambda signal: db.insert_signal(conn, signal),
            )
        except Exception:
            logger.exception("Failed to process submission %s", getattr(submission, "id", "?"))


def run_collector() -> None:
    logging.basicConfig(level=logging.INFO)
    reddit = reddit_client.get_reddit_instance()
    conn = db.get_conn()
    db.init_db(conn)

    sources = ["all"] + config.TARGETED_SUBS
    threads = [
        threading.Thread(target=watch_stream, args=(source, reddit, conn), daemon=True)
        for source in sources
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/projects/demand-researcher && python -m pytest tests/test_collector.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/projects/demand-researcher
git add collector.py tests/test_collector.py
git commit -m "feat: add collector orchestration"
```

---

### Task 6: Flask dashboard

**Files:**
- Create: `app.py`
- Create: `templates/index.html`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `db.get_conn(path)`, `db.init_db(conn)`, `db.get_signals(conn, categorie=None)` (Task 1)
- Produces: `app.create_app(db_path: str | None = None) -> Flask` — factory so tests can inject an isolated DB.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_app.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/projects/demand-researcher && python -m pytest tests/test_app.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Write minimal implementation**

```python
# app.py
from flask import Flask, render_template, request

import db


def create_app(db_path: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path

    @app.route("/")
    def index():
        categorie = request.args.get("categorie") or None
        conn = db.get_conn(app.config["DB_PATH"])
        signals = db.get_signals(conn, categorie=categorie)
        conn.close()
        return render_template("index.html", signals=signals, categorie=categorie)

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
```

```html
<!-- templates/index.html -->
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>Demand Researcher</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border-bottom: 1px solid #ddd; padding: 0.5rem; text-align: left; }
    .produit { color: #0a7d2c; }
    .prestation { color: #1a5fb4; }
    .bruit { color: #999; }
    nav a { margin-right: 1rem; }
  </style>
</head>
<body>
  <h1>Demand Researcher</h1>
  <nav>
    <a href="/">Tout</a>
    <a href="/?categorie=produit">Produits</a>
    <a href="/?categorie=prestation">Prestations</a>
  </nav>
  <table>
    <thead>
      <tr><th>Score</th><th>Catégorie</th><th>Quoi</th><th>Sub</th><th>Lien</th></tr>
    </thead>
    <tbody>
      {% for s in signals %}
      <tr>
        <td>{{ s.score }}</td>
        <td class="{{ s.categorie }}">{{ s.categorie }}</td>
        <td>{{ s.quoi }}</td>
        <td>r/{{ s.sub }}</td>
        <td><a href="{{ s.permalink }}" target="_blank">post</a></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</body>
</html>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/projects/demand-researcher && python -m pytest tests/test_app.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/projects/demand-researcher
git add app.py templates/index.html tests/test_app.py
git commit -m "feat: add Flask dashboard"
```

---

### Task 7: Entrypoint, env template, docs, full manual verification

**Files:**
- Create: `run_collector.py`
- Create: `.env.example`
- Create: `requirements.txt`
- Create: `CLAUDE.md`
- Create: `README.md`

**Interfaces:**
- Consumes: `collector.run_collector()` (Task 5), `app.create_app()` (Task 6)
- Produces: nothing consumed by other tasks — this is the final wiring task.

- [ ] **Step 1: Write `requirements.txt`**

```
praw>=7.7,<8
anthropic>=0.40,<1
flask>=3.0,<4
pytest>=8.0,<9
```

- [ ] **Step 2: Write `.env.example`**

```
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=demand-researcher/0.1 (personal script)
ANTHROPIC_API_KEY=
DEMAND_RESEARCHER_DB=demand_researcher.db
```

- [ ] **Step 3: Write `run_collector.py`**

```python
#!/usr/bin/env python3
"""Entrypoint: start the real-time Reddit demand collector."""
from collector import run_collector

if __name__ == "__main__":
    run_collector()
```

- [ ] **Step 4: Write `CLAUDE.md`**

```markdown
# demand-researcher

Détecte en temps réel sur Reddit les posts qui expriment une demande
("je cherche X") et les classe en `produit` (revendable) ou `prestation`
(service recherché), pour savoir quoi proposer. Outil perso, pas de
compte, pas de SaaS — voir `docs/superpowers/specs/2026-08-28-demand-researcher-design.md`.

## Architecture

- `config.py` — constantes : subs ciblés, mots-clés regex, modèle Claude.
- `db.py` — schéma SQLite (table `signaux`) + insert/lecture avec dédup par `reddit_id`.
- `prefilter.py` — filtre regex d'intention de demande, tourne avant tout
  appel LLM pour maîtriser le coût.
- `classifier.py` — appel Claude Haiku, retourne `{categorie, quoi, score}`.
- `reddit_client.py` — wrapper PRAW (lecture seule), génère un flux de
  submissions pour un subreddit donné.
- `collector.py` — `process_submission()` (pur, testé) applique
  pré-filtre → classification → stockage pour une submission ; `run_collector()`
  lance un thread par source (`r/all` + subs ciblés) et tourne en continu.
- `app.py` + `templates/index.html` — dashboard Flask local, triable/filtrable
  par catégorie.
- `run_collector.py` — entrypoint du collector (à lancer en tâche de fond).

## Lancer

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # puis remplir les clés
export $(cat .env | xargs)
python run_collector.py &   # collecteur en fond
python app.py                # dashboard sur http://127.0.0.1:5000
```
```

- [ ] **Step 5: Write `README.md`**

```markdown
# demand-researcher

Outil perso : détecte sur Reddit des demandes ("je cherche X") pour repérer
des produits à revendre et des prestations recherchées.

Voir `CLAUDE.md` pour l'architecture et le lancement.
```

- [ ] **Step 6: Run the full test suite**

Run: `cd ~/projects/demand-researcher && python -m pytest -v`
Expected: PASS, all tests across `test_db.py`, `test_prefilter.py`, `test_classifier.py`, `test_collector.py`, `test_app.py`.

- [ ] **Step 7: Manual verification of live wiring (requires real credentials)**

1. Create a Reddit app at https://www.reddit.com/prefs/apps (type: "script") to get `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET`.
2. Fill `.env` with real Reddit + `ANTHROPIC_API_KEY` values.
3. Run `python run_collector.py`, let it run a few minutes.
4. In another terminal, run `python app.py` and open `http://127.0.0.1:5000` in Chrome via the claude-in-chrome workflow to confirm rows appear as posts are classified.
5. Confirm the SQLite file `demand_researcher.db` contains rows: `sqlite3 demand_researcher.db "select categorie, quoi, score from signaux order by score desc limit 10;"`

- [ ] **Step 8: Commit**

```bash
cd ~/projects/demand-researcher
git add requirements.txt .env.example run_collector.py CLAUDE.md README.md
git commit -m "feat: add entrypoint, env template, and project docs"
```

---

## Self-Review Notes

- **Spec coverage:** Collecte (§1) → Tasks 4-5; Pré-filtre (§2) → Task 2; Classification (§3) → Task 3; Restitution (§4, dashboard) → Task 6; dédup + stockage complet y compris `bruit` (§3) → Task 1 (`insert_signal` dedup) + Task 5 (`process_submission` always stores whatever the classifier returns, no score threshold). Non-objectifs (pas de push, pas de multi-user, pas d'auth) → nothing in the plan adds any of these.
- **Placeholder scan:** no TBD/TODO; all code blocks are complete and runnable as written.
- **Type consistency:** `signal` dict keys (`reddit_id, sub, title, url, permalink, categorie, quoi, score`) match exactly between `db.insert_signal` (Task 1), `collector.process_submission` (Task 5), and the test fixtures in Tasks 1, 5, 6. `classify_post`/`parse_classification` return shape (`categorie, quoi, score`) matches what `process_submission` consumes.
