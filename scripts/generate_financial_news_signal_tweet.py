"""Generate the Financial News Signal tweet and archive card."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "financial_news_signal.json"
POSTS_FILE = ROOT_DIR / "data" / "posts.json"
TWEET_PREVIEW_FILE = ROOT_DIR / "data" / "financial_news_signal_tweet_preview.txt"
SOURCE_IMAGE = ROOT_DIR / "images" / "financial_news_signal_latest.png"
PUBLIC_POSTS_DIR = ROOT_DIR / "public" / "posts"
WEBSITE_URL = os.environ.get("WEBSITE_URL", "https://qveris.ai")


def short_text(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def format_tweet(data: dict) -> str:
    article_count = int(data.get("article_count") or len(data.get("articles") or []))
    top_ticker = short_text(data.get("top_ticker", "Market"), 18)
    top_topic = short_text(data.get("top_topic", "Financial markets"), 36)
    sentiment = short_text(data.get("dominant_sentiment", "Neutral"), 24)
    top_story = short_text((data.get("articles") or [{}])[0].get("title", "Market headlines pending"), 58)

    lines = [
        "What is the market talking about today? 📰",
        "",
        "Financial News Signal via QVeris:",
        f"🗞️ Headlines scanned: {article_count}",
        f"🏷️ Top ticker: {top_ticker}",
        f"📌 Top theme: {top_topic}",
        f"🧭 Tone: {sentiment}",
        f"🔥 Lead story: {top_story}",
        "",
        f"Live financial news -> research-ready signals ⚡ {WEBSITE_URL}",
    ]
    tweet = "\n".join(lines)
    if len(tweet) > 280:
        lines = [
            "Financial News Signal via QVeris 📰",
            "",
            f"🗞️ Headlines: {article_count}",
            f"🏷️ Ticker: {top_ticker}",
            f"📌 Theme: {short_text(top_topic, 28)}",
            f"🧭 Tone: {sentiment}",
            "",
            f"Signals from live news data: {WEBSITE_URL}",
        ]
        tweet = "\n".join(lines)
    if len(tweet) > 280:
        raise RuntimeError(f"Tweet is {len(tweet)} characters; limit is 280")
    return tweet


def archive_post(data: dict, tweet_text: str) -> None:
    PUBLIC_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    public_image = PUBLIC_POSTS_DIR / f"financial_news_signal_{data['date']}.png"
    shutil.copy2(SOURCE_IMAGE, public_image)

    posts = []
    if POSTS_FILE.exists():
        posts = json.loads(POSTS_FILE.read_text(encoding="utf-8-sig"))

    record = {
        "id": f"financial-news-signal-{data['date']}",
        "date": data["date"],
        "runDate": data["date"],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "contentType": "FINANCIAL NEWS SIGNAL",
        "title": "Financial News Signal",
        "status": "ready",
        "tweet": tweet_text,
        "image": f"/posts/{public_image.name}",
        "dataSource": data.get("source", "QVeris API"),
        "dataUpdatedAt": data.get("updated_at", ""),
        "xPostId": None,
        "primaryLabel": "Top ticker",
        "primaryValue": str(data.get("top_ticker", "Market"))[:32],
        "secondaryLabel": "Tone",
        "secondaryValue": str(data.get("dominant_sentiment", "Neutral"))[:32],
        "topSymbol": str(data.get("top_ticker", "NEWS")),
        "topChangePct": 0,
        "financialNewsSignal": data,
    }

    posts = [post for post in posts if post.get("id") != record["id"]]
    posts.append(record)
    posts.sort(key=lambda post: (post["date"], post.get("createdAt", "")), reverse=True)
    POSTS_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    data = json.loads(DATA_FILE.read_text(encoding="utf-8-sig"))
    tweet_text = format_tweet(data)
    TWEET_PREVIEW_FILE.write_text(tweet_text, encoding="utf-8")
    archive_post(data, tweet_text)

    print("==== Financial News Signal tweet preview ====")
    print(tweet_text)
    print(f"Characters: {len(tweet_text)}")
    print("Status: ready")


if __name__ == "__main__":
    main()
