"""Generate the daily tweet and archive the card."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "rankings.json"
POSTS_FILE = ROOT_DIR / "data" / "posts.json"
TWEET_PREVIEW_FILE = ROOT_DIR / "data" / "tweet_preview.txt"
SOURCE_IMAGE = ROOT_DIR / "images" / "latest.png"
PUBLIC_POSTS_DIR = ROOT_DIR / "public" / "posts"
WEBSITE_URL = os.environ.get("WEBSITE_URL", "https://qveris.ai")


def format_tweet(data: dict) -> str:
    top5 = data["top5"]
    leader = top5[0]
    lines = [
        f"Top 5 liquid U.S. stock movers - {data['date']}",
        "",
        f"Top mover: ${leader['symbol']} {leader['change_pct']:+.2f}%",
        "",
    ]
    lines.extend(
        f"{rank}. ${stock['symbol']} {stock['change_pct']:+.2f}%"
        for rank, stock in enumerate(top5, 1)
    )
    lines.extend(
        [
            "",
            f"More market data: {WEBSITE_URL}",
            "",
            "Information only. Not investment advice.",
            "#Stocks #MarketData",
        ]
    )
    tweet = "\n".join(lines)
    if len(tweet) > 280:
        raise RuntimeError(f"Tweet is {len(tweet)} characters; limit is 280")
    return tweet


def archive_post(data: dict, tweet_text: str, status: str, x_post_id: str | None) -> None:
    PUBLIC_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    public_image = PUBLIC_POSTS_DIR / f"top5_{data['date']}.png"
    shutil.copy2(SOURCE_IMAGE, public_image)

    posts = []
    if POSTS_FILE.exists():
        posts = json.loads(POSTS_FILE.read_text(encoding="utf-8-sig"))

    top = data["top5"][0]
    record = {
        "id": f"market-pulse-{data['date']}",
        "date": data["date"],
        "runDate": data["date"],
        "marketDate": data.get("market_date") or data["date"],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "contentType": "MARKET PULSE",
        "title": "Top 5 Liquid U.S. Stock Movers",
        "status": status,
        "tweet": tweet_text,
        "image": f"/posts/{public_image.name}",
        "dataSource": data.get("source", "QVeris API"),
        "dataUpdatedAt": data.get("last_updated_label", ""),
        "xPostId": x_post_id,
        "top5": data["top5"],
        "topSymbol": top["symbol"],
        "topChangePct": top["change_pct"],
    }

    posts = [post for post in posts if post.get("id") != record["id"]]
    posts.append(record)
    posts.sort(key=lambda post: post["date"], reverse=True)
    POSTS_FILE.write_text(
        json.dumps(posts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    tweet_text = format_tweet(data)
    TWEET_PREVIEW_FILE.write_text(tweet_text, encoding="utf-8")

    archive_post(data, tweet_text, "ready", None)

    print("==== Tweet preview ====")
    print(tweet_text)
    print(f"Characters: {len(tweet_text)}")
    print("Status: ready")


if __name__ == "__main__":
    main()
