"""Generate the Market Narrative Shift tweet and archive card."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "market_narrative_shift.json"
POSTS_FILE = ROOT_DIR / "data" / "posts.json"
TWEET_FILE = ROOT_DIR / "data" / "market_narrative_shift_tweet_preview.txt"
SOURCE_IMAGE = ROOT_DIR / "images" / "market_narrative_shift_latest.png"
PUBLIC_POSTS_DIR = ROOT_DIR / "public" / "posts"
WEBSITE_URL = os.environ.get("WEBSITE_URL", "https://qveris.ai")


def short_text(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def format_tweet(data: dict) -> str:
    current = data.get("current") or {}
    previous = data.get("previous") or {}
    symbol = data.get("symbol", "Market")
    emerging = (data.get("emerging_keywords") or data.get("emerging_themes") or ["baseline"])[0]
    delta = f"{float(data.get('sentiment_delta') or 0):+.2f}" if previous else "baseline"
    lines = [
        f"What changed in ${symbol}'s market narrative? 🔄",
        "",
        f"🧭 Signal: {data.get('shift_label', 'Narrative steady')}",
        f"💬 Sentiment shift: {delta}",
        f"📌 Top theme: {short_text(current.get('top_theme', 'Financial Markets'), 30)}",
        f"🔎 Emerging term: {short_text(emerging, 24)}",
        f"📰 Coverage: {current.get('article_count', 0)} vs {previous.get('article_count', 'n/a')}",
        "",
        f"Narrative intelligence via QVeris: {WEBSITE_URL}",
    ]
    tweet = "\n".join(lines)
    if len(tweet) > 280:
        lines.pop(5)
        tweet = "\n".join(lines)
    if len(tweet) > 280:
        raise RuntimeError(f"Tweet is {len(tweet)} characters; limit is 280")
    return tweet


def archive_post(data: dict, tweet: str) -> None:
    PUBLIC_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    symbol = str(data["symbol"]).upper()
    public_image = PUBLIC_POSTS_DIR / f"market_narrative_shift_{symbol}_{data['date']}.png"
    shutil.copy2(SOURCE_IMAGE, public_image)
    posts = json.loads(POSTS_FILE.read_text(encoding="utf-8-sig")) if POSTS_FILE.exists() else []
    record = {
        "id": f"market-narrative-shift-{symbol.lower()}-{data['date']}",
        "date": data["date"],
        "runDate": data["date"],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "contentType": "MARKET NARRATIVE SHIFT",
        "title": f"Market Narrative Shift: ${symbol}",
        "status": "ready",
        "tweet": tweet,
        "image": f"/posts/{public_image.name}",
        "dataSource": data.get("source", "QVeris API"),
        "dataUpdatedAt": data.get("updated_at", ""),
        "xPostId": None,
        "primaryLabel": "Ticker",
        "primaryValue": f"${symbol}",
        "secondaryLabel": "Shift",
        "secondaryValue": data.get("shift_label", "Narrative steady"),
        "topSymbol": symbol,
        "topChangePct": float(data.get("sentiment_delta") or 0.0) * 100,
        "marketNarrativeShift": data,
    }
    posts = [post for post in posts if post.get("id") != record["id"]]
    posts.append(record)
    posts.sort(key=lambda post: (post["date"], post.get("createdAt", "")), reverse=True)
    POSTS_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data = json.loads(DATA_FILE.read_text(encoding="utf-8-sig"))
    tweet = format_tweet(data)
    TWEET_FILE.write_text(tweet, encoding="utf-8")
    archive_post(data, tweet)
    print("==== Market Narrative Shift tweet preview ====")
    print(tweet)
    print(f"Characters: {len(tweet)}")


if __name__ == "__main__":
    main()
