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
