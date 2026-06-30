"""Generate the prediction-market pulse tweet and archive card."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "prediction_markets.json"
POSTS_FILE = ROOT_DIR / "data" / "posts.json"
TWEET_PREVIEW_FILE = ROOT_DIR / "data" / "prediction_market_tweet_preview.txt"
SOURCE_IMAGE = ROOT_DIR / "images" / "prediction_market_latest.png"
PUBLIC_POSTS_DIR = ROOT_DIR / "public" / "posts"
WEBSITE_URL = os.environ.get("WEBSITE_URL", "https://qveris.ai")


def pct(value: float) -> str:
    return f"{value:.1f}%"


def pts(value: float) -> str:
    return f"{value:+.1f} pts"


def short_title(value: str, max_len: int = 54) -> str:
    value = " ".join(str(value).split())
    if len(value) <= max_len:
        return value
    return value[: max_len - 3].rstrip() + "..."


def format_tweet(data: dict) -> str:
    markets = data.get("markets", [])[:3]
    has_any_probability = any(market.get("has_probability", True) for market in markets)
    lines = [
        "Prediction markets are moving today.",
        "",
        "Biggest probability signals:" if has_any_probability else "Active markets to watch:",
    ]
    for index, market in enumerate(markets, 1):
        if market.get("has_probability", True):
            lines.append(
                f"{index}. {short_title(market['title'])}: "
                f"{pct(float(market['probability']))} ({pts(float(market.get('probability_change', 0)))})"
            )
        else:
            lines.append(f"{index}. {short_title(market['title'])}")
    lines.extend(
        [
            "",
            "Not a forecast. Just what prediction markets are surfacing.",
            "",
            f"Built with QVeris: {WEBSITE_URL}",
        ]
    )
    tweet = "\n".join(lines)
    if len(tweet) > 280:
        lines = [
            "Prediction Market Pulse",
            "",
            *[
                (
                    f"{index}. {short_title(market['title'], 42)}: {pct(float(market['probability']))}"
                    if market.get("has_probability", True)
                    else f"{index}. {short_title(market['title'], 48)}"
                )
                for index, market in enumerate(markets, 1)
            ],
            "",
            "Market-implied probabilities. Built with QVeris.",
        ]
        tweet = "\n".join(lines)
    if len(tweet) > 280:
        raise RuntimeError(f"Tweet is {len(tweet)} characters; limit is 280")
    return tweet


def archive_post(data: dict, tweet_text: str) -> None:
    PUBLIC_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    public_image = PUBLIC_POSTS_DIR / f"prediction_market_{data['date']}.png"
    shutil.copy2(SOURCE_IMAGE, public_image)

    posts = []
    if POSTS_FILE.exists():
        posts = json.loads(POSTS_FILE.read_text(encoding="utf-8"))

    markets = data.get("markets", [])
    leader = markets[0]
    runner_up = markets[1] if len(markets) > 1 else None
    leader_value = (
        pct(float(leader["probability"]))
        if leader.get("has_probability", True)
        else "Watching"
    )
    runner_up_value = (
        pct(float(runner_up["probability"]))
        if runner_up and runner_up.get("has_probability", True)
        else "Watching"
        if runner_up
        else str(len(markets))
    )
    record = {
        "id": f"prediction-market-pulse-{data['date']}",
        "date": data["date"],
        "runDate": data["date"],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "contentType": "PREDICTION MARKET",
        "title": "Prediction Market Pulse",
        "status": "ready",
        "tweet": tweet_text,
        "image": f"/posts/{public_image.name}",
        "dataSource": data.get("source", "QVeris API"),
        "dataUpdatedAt": data.get("updated_at", ""),
        "xPostId": None,
        "primaryLabel": short_title(leader["title"], 32),
        "primaryValue": leader_value,
        "secondaryLabel": short_title(runner_up["title"], 32) if runner_up else "Markets tracked",
        "secondaryValue": runner_up_value,
        "topSymbol": "PM",
        "topChangePct": float(leader.get("probability_change", 0)),
        "predictionMarket": data,
    }

    posts = [post for post in posts if post.get("id") != record["id"]]
    posts.append(record)
    posts.sort(key=lambda post: (post["date"], post.get("createdAt", "")), reverse=True)
    POSTS_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    tweet_text = format_tweet(data)
    TWEET_PREVIEW_FILE.write_text(tweet_text, encoding="utf-8")
    archive_post(data, tweet_text)

    print("==== Prediction Market tweet preview ====")
    print(tweet_text)
    print(f"Characters: {len(tweet_text)}")
    print("Status: ready")


if __name__ == "__main__":
    main()
