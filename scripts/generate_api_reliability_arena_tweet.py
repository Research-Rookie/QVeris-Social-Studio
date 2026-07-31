"""Generate the API Reliability Arena tweet and append its archive card."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "api_reliability_arena.json"
POSTS_FILE = ROOT_DIR / "data" / "posts.json"
TWEET_FILE = ROOT_DIR / "data" / "api_reliability_arena_tweet_preview.txt"
SOURCE_IMAGE = ROOT_DIR / "images" / "api_reliability_arena_latest.png"
PUBLIC_DIR = ROOT_DIR / "public" / "posts"
WEBSITE_URL = os.environ.get("WEBSITE_URL", "https://qveris.ai")


def short(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def format_tweet(data: dict) -> str:
    champion = data.get("champion") or {}
    success = champion.get("success_rate")
    latency = champion.get("latency_ms")
    cost = champion.get("cost_credits")
    success_text = f"{float(success) * 100:.1f}% success" if success is not None else "success n/a"
    latency_text = f"{float(latency):,.0f}ms" if latency is not None else "latency n/a"
    expected_cost_text = str(champion.get("expected_cost_text") or "").lower()
    if cost is not None and float(cost) == 0 and "free" in expected_cost_text:
        cost_text = "Free"
    else:
        cost_text = f"{float(cost):g} credits" if cost is not None else "cost n/a"
    tweet = "\n".join([
        "Which API would an AI agent choose? ⚔️",
        "",
        f"Today's task: {short((data.get('scenario') or {}).get('label'), 34)}",
        f"🏆 {short(champion.get('name'), 44)}",
        f"✅ {success_text} | ⚡ {latency_text} | 🪙 {cost_text}",
        "",
        "QVeris compares routing signals before the call, so agents can choose with evidence.",
        WEBSITE_URL,
    ])
    if len(tweet) > 280:
        tweet = tweet.replace("QVeris compares routing signals before the call, so agents can choose with evidence.", "Choose finance APIs with routing evidence via QVeris.")
    if len(tweet) > 280:
        raise RuntimeError(f"Tweet is {len(tweet)} characters; limit is 280")
    return tweet


def archive(data: dict, tweet: str) -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    scenario = data.get("scenario") or {}
    scenario_key = scenario.get("key", "finance")
    filename = f"api_reliability_arena_{scenario_key}_{data['date']}.png"
    shutil.copy2(SOURCE_IMAGE, PUBLIC_DIR / filename)
    posts = json.loads(POSTS_FILE.read_text(encoding="utf-8-sig")) if POSTS_FILE.exists() else []
    champion = data.get("champion") or {}
    record = {
        "id": f"api-reliability-arena-{scenario_key}-{data['date']}",
        "date": data["date"],
        "runDate": data["date"],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "contentType": "API RELIABILITY ARENA",
        "title": f"API Reliability Arena: {scenario.get('label', 'Finance APIs')}",
        "status": "ready",
        "tweet": tweet,
        "image": f"/posts/{filename}",
        "dataSource": data.get("source", "QVeris Discover routing signals"),
        "dataUpdatedAt": data.get("updated_at", ""),
        "xPostId": None,
        "primaryLabel": "Champion",
        "primaryValue": short(champion.get("name", "Not ranked"), 36),
        "secondaryLabel": "Route score",
        "secondaryValue": f"{float(champion.get('route_score') or 0):.1f}",
        "topSymbol": "API",
        "topChangePct": float(champion.get("route_score") or 0),
        "apiReliabilityArena": data,
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
