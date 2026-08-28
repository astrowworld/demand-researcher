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
