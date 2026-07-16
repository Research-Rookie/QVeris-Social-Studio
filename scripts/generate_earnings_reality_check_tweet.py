"""Generate Earnings Reality Check tweet and append its archive card."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "earnings_reality_check.json"
POSTS_FILE = ROOT_DIR / "data" / "posts.json"
TWEET_FILE = ROOT_DIR / "data" / "earnings_reality_check_tweet_preview.txt"
SOURCE_IMAGE = ROOT_DIR / "images" / "earnings_reality_check_latest.png"
PUBLIC_DIR = ROOT_DIR / "public" / "posts"
WEBSITE_URL = os.environ.get("WEBSITE_URL", "https://qveris.ai")


def format_tweet(data: dict) -> str:
    reaction = data.get("price_reaction") or {}
    move = f"{float(reaction.get('change_pct') or 0):+.2f}%" if reaction.get("available") else "pending"
    tweet = "\n".join([
        "The earnings headline is only half the story. 👀",
        "",
        f"${data['symbol']} EPS: ${float(data['actual_eps']):.2f} vs ${float(data['estimated_eps']):.2f} est. ({float(data['surprise_pct']):+.1f}%)",
        f"📈 Next-session reaction: {move}",
        f"🧭 Reality check: {data['verdict']}",
        "",
        "Numbers show the result. Price shows the market's verdict.",
        f"Built with QVeris: {WEBSITE_URL}",
    ])
    if len(tweet) > 280:
        tweet = tweet.replace("The earnings headline is only half the story. 👀", "Did the market believe the earnings? 👀")
    if len(tweet) > 280:
        raise RuntimeError(f"Tweet is {len(tweet)} characters; limit is 280")
    return tweet


def archive(data: dict, tweet: str) -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    symbol = str(data["symbol"]).upper()
    filename = f"earnings_reality_check_{symbol}_{data['reported_date']}.png"
    public_image = PUBLIC_DIR / filename
    shutil.copy2(SOURCE_IMAGE, public_image)
    posts = json.loads(POSTS_FILE.read_text(encoding="utf-8-sig")) if POSTS_FILE.exists() else []
    record = {
        "id": f"earnings-reality-check-{symbol.lower()}-{data['reported_date']}",
        "date": data["date"],
        "runDate": data["date"],
        "marketDate": data["reported_date"],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "contentType": "EARNINGS REALITY CHECK",
        "title": f"Earnings Reality Check: ${symbol}",
        "status": "ready",
        "tweet": tweet,
        "image": f"/posts/{filename}",
        "dataSource": data.get("source", "QVeris API"),
        "dataUpdatedAt": data.get("updated_at", ""),
        "xPostId": None,
        "primaryLabel": "EPS surprise",
        "primaryValue": f"{float(data.get('surprise_pct') or 0):+.1f}%",
        "secondaryLabel": "Verdict",
        "secondaryValue": data.get("verdict", "Mixed reaction"),
        "topSymbol": symbol,
        "topChangePct": float((data.get("price_reaction") or {}).get("change_pct") or 0),
        "earningsRealityCheck": data,
    }
    posts = [post for post in posts if post.get("id") != record["id"]]
    posts.append(record)
    posts.sort(key=lambda post: (post.get("date", ""), post.get("createdAt", "")), reverse=True)
    POSTS_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data = json.loads(DATA_FILE.read_text(encoding="utf-8-sig"))
    tweet = format_tweet(data)
    TWEET_FILE.write_text(tweet, encoding="utf-8")
    archive(data, tweet)
    print(tweet)
    print(f"Characters: {len(tweet)}")


if __name__ == "__main__":
    main()
