"""Generate World Cup finance signal tweet and archive card."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "world_cup_finance.json"
POSTS_FILE = ROOT_DIR / "data" / "posts.json"
TWEET_PREVIEW_FILE = ROOT_DIR / "data" / "world_cup_finance_tweet_preview.txt"
SOURCE_IMAGE = ROOT_DIR / "images" / "world_cup_finance_latest.png"
PUBLIC_POSTS_DIR = ROOT_DIR / "public" / "posts"
WEBSITE_URL = os.environ.get("WEBSITE_URL", "https://qveris.ai")


def pct(value: float) -> str:
    return f"{value:+.2f}%"


def format_tweet(data: dict) -> str:
    leader = data["leader"]
    theme = data["top_theme"]
    top_stocks = data["stocks"][:4]
    lines = [
        f"World Cup Finance Signals - {data['date']}",
        "",
        f"Latest match: {data['match_label']}",
        f"Basket leader: ${leader['symbol']} {pct(leader['change_pct'])}",
        f"Top theme: {theme['name']} {pct(theme['avg_change_pct'])} avg",
        "",
    ]
    lines.extend(
        f"${stock['symbol']} {pct(stock['change_pct'])}"
        for stock in top_stocks
    )
    lines.extend(
        [
            "",
            f"More market data: {WEBSITE_URL}",
            "Information only. Not investment advice.",
        ]
    )
    tweet = "\n".join(lines)
    if len(tweet) > 280:
        raise RuntimeError(f"Tweet is {len(tweet)} characters; limit is 280")
    return tweet


def archive_post(data: dict, tweet_text: str) -> None:
    PUBLIC_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    public_image = PUBLIC_POSTS_DIR / f"world_cup_finance_{data['date']}.png"
    shutil.copy2(SOURCE_IMAGE, public_image)

    posts = []
    if POSTS_FILE.exists():
        posts = json.loads(POSTS_FILE.read_text(encoding="utf-8"))

    leader = data["leader"]
    theme = data["top_theme"]
    record = {
        "id": f"world-cup-finance-{data['date']}",
        "date": data["date"],
        "runDate": data["date"],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "contentType": "WORLD CUP FINANCE",
        "title": "World Cup Finance Signals",
        "status": "ready",
        "tweet": tweet_text,
        "image": f"/posts/{public_image.name}",
        "dataSource": data.get("source", "Financial Modeling Prep"),
        "dataUpdatedAt": data.get("updated_at", ""),
        "xPostId": None,
        "primaryLabel": f"${leader['symbol']} daily move",
        "primaryValue": pct(leader["change_pct"]),
        "secondaryLabel": f"{theme['name']} avg",
        "secondaryValue": pct(theme["avg_change_pct"]),
        "topSymbol": leader["symbol"],
        "topChangePct": leader["change_pct"],
        "worldCupFinance": data,
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
    archive_post(data, tweet_text)

    print("==== World Cup finance tweet preview ====")
    print(tweet_text)
    print(f"Characters: {len(tweet_text)}")
    print("Status: ready")


if __name__ == "__main__":
    main()
