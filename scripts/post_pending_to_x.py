"""Publish pending archived cards to X.

The script is intentionally opt-in. Set X_AUTO_POST=true in the workflow
environment to publish; otherwise it prints a dry-run preview and exits.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT_DIR = Path(__file__).resolve().parent.parent
POSTS_FILE = ROOT_DIR / "data" / "posts.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")


def env_flag(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def run_date() -> str:
    return os.environ.get("X_POST_DATE") or datetime.now(RUN_TIMEZONE).strftime("%Y-%m-%d")


def required_credentials() -> list[str]:
    return [
        "X_API_KEY",
        "X_API_SECRET",
        "X_ACCESS_TOKEN",
        "X_ACCESS_SECRET",
    ]


def image_path(post: dict) -> Path:
    image = str(post.get("image") or "").lstrip("/")
    if not image:
        raise RuntimeError(f"Post {post.get('id')} does not include an image")
    path = ROOT_DIR / "public" / image
    if not path.exists():
        raise RuntimeError(f"Image not found for post {post.get('id')}: {path}")
    return path


def load_posts() -> list[dict]:
    if not POSTS_FILE.exists():
        return []
    return json.loads(POSTS_FILE.read_text(encoding="utf-8"))


def find_pending(posts: list[dict]) -> list[dict]:
    content_type = os.environ.get("X_POST_CONTENT_TYPE", "").strip()
    date = run_date()
    limit = int(os.environ.get("X_POST_LIMIT", "10"))

    pending = []
    for post in posts:
        if post.get("date") != date:
            continue
        if content_type and post.get("contentType") != content_type:
            continue
        if post.get("xPostId"):
            continue
        if post.get("status") not in {"ready", "published"}:
            continue
        pending.append(post)

    pending.sort(key=lambda item: item.get("createdAt", ""))
    return pending[:limit]


def publish_to_x(tweet_text: str, media_path: Path) -> str:
    import tweepy

    missing = [name for name in required_credentials() if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing X credentials: {', '.join(missing)}")

    auth = tweepy.OAuth1UserHandler(
        os.environ["X_API_KEY"],
        os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_SECRET"],
    )
    media = tweepy.API(auth).media_upload(str(media_path))
    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )
    response = client.create_tweet(text=tweet_text, media_ids=[media.media_id])
    return str(response.data["id"])


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    posts = load_posts()
    pending = find_pending(posts)
    should_post = env_flag("X_AUTO_POST")

    if not pending:
        print("No pending X posts found.")
        return

    print(f"Pending X posts: {len(pending)}")
    for post in pending:
        print(f"- {post['id']} | {post.get('title')} | {len(post.get('tweet', ''))} chars")

    if not should_post:
        print("X_AUTO_POST is not true. Dry run only; nothing was published.")
        return

    published = 0
    for post in pending:
        tweet_text = post.get("tweet", "")
        if not tweet_text:
            raise RuntimeError(f"Post {post.get('id')} does not include tweet text")
        if len(tweet_text) > 280:
            raise RuntimeError(f"Post {post.get('id')} tweet is {len(tweet_text)} characters")

        x_post_id = publish_to_x(tweet_text, image_path(post))
        post["xPostId"] = x_post_id
        post["status"] = "published"
        published += 1
        print(f"Published {post['id']} to X: {x_post_id}")

    POSTS_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Published {published} post(s) to X.")


if __name__ == "__main__":
    main()
