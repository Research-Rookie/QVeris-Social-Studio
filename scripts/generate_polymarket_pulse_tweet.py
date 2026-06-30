"""Generate the Polymarket activity pulse tweet and archive card."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "polymarket_pulse.json"
POSTS_FILE = ROOT_DIR / "data" / "posts.json"
TWEET_PREVIEW_FILE = ROOT_DIR / "data" / "polymarket_pulse_tweet_preview.txt"
SOURCE_IMAGE = ROOT_DIR / "images" / "polymarket_pulse_latest.png"
PUBLIC_POSTS_DIR = ROOT_DIR / "public" / "posts"
WEBSITE_URL = os.environ.get("WEBSITE_URL", "https://qveris.ai")


def money_short(value: float) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    if value > 0:
        return f"${value:.0f}"
    return "n/a"


def format_tweet(data: dict) -> str:
    volume = money_short(float(data.get("current_volume", 0)))
    change = float(data.get("volume_change_pct", 0))
    open_interest = money_short(float(data.get("open_interest", 0)))
    label = data.get("activity_label", "Stable")
    volume_available = bool(data.get("volume_available", True))
    volume_line = (
        f"- Volume: {volume} ({change:+.1f}%)"
        if volume_available
        else f"- Activity snapshot: {volume}"
    )
    lines = [
        "Prediction markets are becoming a real-time sentiment layer.",
        "",
        "Today's Polymarket activity pulse:",
        volume_line,
        f"- Open interest: {open_interest}",
        f"- Signal: {label}",
        "",
        f"Built with QVeris: {WEBSITE_URL}",
    ]
    tweet = "\n".join(lines)
    if len(tweet) > 280:
        lines = [
            "Polymarket Activity Pulse",
            "",
            volume_line.replace("- ", ""),
            f"Open interest: {open_interest}",
            f"Signal: {label}",
            "",
            "Built with QVeris.",
        ]
        tweet = "\n".join(lines)
    if len(tweet) > 280:
        raise RuntimeError(f"Tweet is {len(tweet)} characters; limit is 280")
    return tweet


def archive_post(data: dict, tweet_text: str) -> None:
    PUBLIC_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    public_image = PUBLIC_POSTS_DIR / f"polymarket_pulse_{data['date']}.png"
    shutil.copy2(SOURCE_IMAGE, public_image)

    posts = []
    if POSTS_FILE.exists():
        posts = json.loads(POSTS_FILE.read_text(encoding="utf-8-sig"))

    record = {
        "id": f"polymarket-pulse-{data['date']}",
        "date": data["date"],
        "runDate": data["date"],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "contentType": "POLYMARKET PULSE",
        "title": "Polymarket Activity Pulse",
        "status": "ready",
        "tweet": tweet_text,
        "image": f"/posts/{public_image.name}",
        "dataSource": data.get("source", "QVeris API"),
        "dataUpdatedAt": data.get("updated_at", ""),
        "xPostId": None,
        "primaryLabel": "Volume",
        "primaryValue": money_short(float(data.get("current_volume", 0))),
        "secondaryLabel": "Open interest",
        "secondaryValue": money_short(float(data.get("open_interest", 0))),
        "topSymbol": "PM",
        "topChangePct": float(data.get("volume_change_pct", 0)),
        "polymarketPulse": data,
    }

    posts = [
        post
        for post in posts
        if post.get("id") != record["id"]
        and post.get("contentType") not in {"PREDICTION MARKET", "WORLD CUP FINANCE"}
    ]
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

    print("==== Polymarket tweet preview ====")
    print(tweet_text)
    print(f"Characters: {len(tweet_text)}")
    print("Status: ready")


if __name__ == "__main__":
    main()
