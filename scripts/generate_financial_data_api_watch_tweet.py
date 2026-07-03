"""Generate the Financial Data API Watch tweet and archive card."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "financial_data_api_watch.json"
POSTS_FILE = ROOT_DIR / "data" / "posts.json"
TWEET_PREVIEW_FILE = ROOT_DIR / "data" / "financial_data_api_watch_tweet_preview.txt"
SOURCE_IMAGE = ROOT_DIR / "images" / "financial_data_api_watch_latest.png"
PUBLIC_POSTS_DIR = ROOT_DIR / "public" / "posts"
WEBSITE_URL = os.environ.get("WEBSITE_URL", "https://qveris.ai")


def short_text(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def format_tweet(data: dict) -> str:
    companies = data.get("companies") or []
    left = companies[0] if companies else {"symbol": "A", "latest_fcf_yield": 0}
    right = companies[1] if len(companies) > 1 else {"symbol": "B", "latest_fcf_yield": 0}
    news = data.get("news") or {}
    brain = "\U0001f9e0"
    chart = "\U0001f4ca"
    building = "\U0001f3e2"
    money = "\U0001f4b0"
    news_icon = "\U0001f4f0"

    lines = [
        f"What can an AI finance agent do with one QVeris workflow? {brain}",
        "",
        f"Today: compare ${left['symbol']} vs ${right['symbol']}",
        "",
        "QVeris connected:",
        f"{chart} Financial fundamentals",
        f"{building} Market cap",
        f"{money} FCF yield",
        f"{news_icon} News signal",
        "",
        f"Output: {left['symbol']} {left.get('latest_fcf_yield', 0):.1f}% vs {right['symbol']} {right.get('latest_fcf_yield', 0):.1f}% FCF yield",
        f"News: {short_text(news.get('top_ticker', 'Market'), 16)} / {short_text(news.get('tone', 'Neutral'), 20)}",
        "",
        WEBSITE_URL,
    ]
    tweet = "\n".join(lines)
    if len(tweet) > 280:
        lines = [
            "AI finance agents need more than one API.",
            "",
            f"QVeris workflow: ${left['symbol']} vs ${right['symbol']}",
            f"{chart} Fundamentals",
            f"{building} Market cap",
            f"{money} FCF yield",
            f"{news_icon} News signal",
            "",
            f"From API discovery to research-ready output: {WEBSITE_URL}",
        ]
        tweet = "\n".join(lines)
    if len(tweet) > 280:
        raise RuntimeError(f"Tweet is {len(tweet)} characters; limit is 280")
    return tweet


def archive_post(data: dict, tweet_text: str) -> None:
    PUBLIC_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    public_image = PUBLIC_POSTS_DIR / f"financial_data_api_watch_{data['date']}.png"
    shutil.copy2(SOURCE_IMAGE, public_image)

    posts = []
    if POSTS_FILE.exists():
        posts = json.loads(POSTS_FILE.read_text(encoding="utf-8-sig"))

    symbols = "-".join(data.get("symbols") or ["api", "watch"]).lower()
    companies = data.get("companies") or [{}, {}]
    left = companies[0] if companies else {}
    right = companies[1] if len(companies) > 1 else {}
    record = {
        "id": f"financial-data-api-watch-{symbols}-{data['date']}",
        "date": data["date"],
        "runDate": data["date"],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "contentType": "FINANCIAL DATA API WATCH",
        "title": "Financial Data API Watch",
        "status": "ready",
        "tweet": tweet_text,
        "image": f"/posts/{public_image.name}",
        "dataSource": data.get("source", "QVeris API"),
        "dataUpdatedAt": data.get("updated_at", ""),
        "xPostId": None,
        "primaryLabel": "Agent task",
        "primaryValue": str(data.get("scenario", "Workflow"))[:32],
        "secondaryLabel": "Comparison",
        "secondaryValue": f"{left.get('symbol', 'A')} vs {right.get('symbol', 'B')}",
        "topSymbol": left.get("symbol", "API"),
        "topChangePct": float(left.get("latest_fcf_yield", 0) or 0),
        "financialDataApiWatch": data,
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
    print("==== Financial Data API Watch tweet preview ====")
    print(tweet_text)
    print(f"Characters: {len(tweet_text)}")
    print("Status: ready")


if __name__ == "__main__":
    main()
