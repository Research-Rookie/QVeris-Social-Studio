"""Generate a Live API Battle tweet and append its archive card."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "live_api_battle.json"
POSTS_FILE = ROOT_DIR / "data" / "posts.json"
TWEET_FILE = ROOT_DIR / "data" / "live_api_battle_tweet_preview.txt"
SOURCE_IMAGE = ROOT_DIR / "images" / "live_api_battle_latest.png"
PUBLIC_DIR = ROOT_DIR / "public" / "posts"
WEBSITE_URL = os.environ.get("WEBSITE_URL", "https://qveris.ai")


def short(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def format_tweet(data: dict) -> str:
    winner = data.get("winner") or {}
    usable_count = len([
        item for item in data.get("participants") or []
        if item.get("success") and float(item.get("completeness") or 0) > 0
    ])
    spread = data.get("price_spread_pct")
    lines = [
        f"{usable_count} live APIs answered the same market question. One won. \U0001f94a",
        "",
        short(data.get("question"), 58),
        f"\U0001f3c6 Winner: {short(winner.get('provider'), 35)}",
        f"\u26a1 {int(winner.get('latency_ms') or 0):,}ms | \U0001f9e9 {float(winner.get('completeness') or 0):.0%} fields | \U0001f552 {winner.get('freshness_label', 'n/a')}",
    ]
    if spread is not None:
        lines.append(f"\U0001f4ca Price spread across responses: {float(spread):.2f}%")
    lines.extend(["", f"Live API comparison via QVeris: {WEBSITE_URL}"])
    tweet = "\n".join(lines)
    if len(tweet) > 280:
        tweet = tweet.replace(f"{usable_count} live APIs answered the same market question. One won. \U0001f94a", "Same question. Live APIs compared. One winner. \U0001f94a")
    if len(tweet) > 280:
        tweet = tweet.replace("Live API comparison via QVeris", "Built with QVeris")
    if len(tweet) > 280:
        raise RuntimeError(f"Tweet is {len(tweet)} characters; limit is 280")
    return tweet


def archive(data: dict, tweet: str) -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    symbol = str((data.get("scenario") or {}).get("symbol") or "market").upper()
    filename = f"live_api_battle_{symbol.lower()}_{data['date']}.png"
    shutil.copy2(SOURCE_IMAGE, PUBLIC_DIR / filename)
    posts = json.loads(POSTS_FILE.read_text(encoding="utf-8-sig")) if POSTS_FILE.exists() else []
    winner = data.get("winner") or {}
    record = {
        "id": f"live-api-battle-{symbol.lower()}-{data['date']}",
        "date": data["date"],
        "runDate": data["date"],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "contentType": "LIVE API BATTLE",
        "title": f"Live API Battle: ${symbol}",
        "status": "ready",
        "tweet": tweet,
        "image": f"/posts/{filename}",
        "dataSource": data.get("source", "Live calls through QVeris API"),
        "dataUpdatedAt": data.get("updated_at", ""),
        "xPostId": None,
        "primaryLabel": "Winner",
        "primaryValue": short(winner.get("provider", "No winner"), 32),
        "secondaryLabel": "Live latency",
        "secondaryValue": f"{int(winner.get('latency_ms') or 0):,}ms",
        "topSymbol": symbol,
        "topChangePct": float(winner.get("battle_score") or 0),
        "liveApiBattle": data,
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
