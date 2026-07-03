"""Generate the News vs Price Reaction tweet and archive card."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "news_vs_price_reaction.json"
POSTS_FILE = ROOT_DIR / "data" / "posts.json"
TWEET_PREVIEW_FILE = ROOT_DIR / "data" / "news_vs_price_reaction_tweet_preview.txt"
SOURCE_IMAGE = ROOT_DIR / "images" / "news_vs_price_reaction_latest.png"
PUBLIC_POSTS_DIR = ROOT_DIR / "public" / "posts"
WEBSITE_URL = os.environ.get("WEBSITE_URL", "https://qveris.ai")


def short_text(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def signed_pct(value: object) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    return f"{number:+.2f}%"


def format_tweet(data: dict) -> str:
    eyes = "\U0001f440"
    newspaper = "\U0001f4f0"
    chart = "\U0001f4c8"
    signal = "\U0001f4a1"
    symbol = data.get("symbol", "MARKET")
    lines = [
        f"Good news does not always mean green candles. {eyes}",
        "",
        f"${symbol} news vs price reaction:",
        f"{newspaper} News tone: {short_text(data.get('news_tone', 'Neutral'), 24)}",
        f"{chart} Price move: {signed_pct(data.get('change_pct', 0))}",
        f"{signal} Signal: {short_text(data.get('reaction_label', 'Watching'), 42)}",
        "",
        short_text(data.get("takeaway", ""), 96),
        "",
        f"Built with QVeris: {WEBSITE_URL}",
    ]
    tweet = "\n".join(lines)
    if len(tweet) > 280:
        lines = [
            f"${symbol}: news vs price reaction",
            "",
            f"News tone: {short_text(data.get('news_tone', 'Neutral'), 24)}",
            f"Price move: {signed_pct(data.get('change_pct', 0))}",
            f"Signal: {short_text(data.get('reaction_label', 'Watching'), 42)}",
            "",
            f"Built with QVeris: {WEBSITE_URL}",
        ]
        tweet = "\n".join(lines)
    if len(tweet) > 280:
        raise RuntimeError(f"Tweet is {len(tweet)} characters; limit is 280")
    return tweet


def archive_post(data: dict, tweet_text: str) -> None:
    PUBLIC_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    public_image = PUBLIC_POSTS_DIR / f"news_vs_price_reaction_{data['date']}.png"
    shutil.copy2(SOURCE_IMAGE, public_image)

    posts = []
    if POSTS_FILE.exists():
        posts = json.loads(POSTS_FILE.read_text(encoding="utf-8-sig"))

    symbol = data.get("symbol", "MARKET")
    record = {
        "id": f"news-vs-price-reaction-{str(symbol).lower()}-{data['date']}",
        "date": data["date"],
        "runDate": data["date"],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "contentType": "NEWS VS PRICE REACTION",
        "title": "News vs Price Reaction",
        "status": "ready",
        "tweet": tweet_text,
        "image": f"/posts/{public_image.name}",
        "dataSource": data.get("source", "QVeris API"),
        "dataUpdatedAt": data.get("updated_at", ""),
        "xPostId": None,
        "primaryLabel": "Ticker",
        "primaryValue": f"${symbol}",
        "secondaryLabel": "Signal",
        "secondaryValue": str(data.get("reaction_label", "Watching"))[:32],
        "topSymbol": symbol,
        "topChangePct": float(data.get("change_pct", 0) or 0),
        "newsVsPriceReaction": data,
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
    print("==== News vs Price Reaction tweet preview ====")
    print(tweet_text)
    print(f"Characters: {len(tweet_text)}")
    print("Status: ready")


if __name__ == "__main__":
    main()
