"""Generate the Prediction Market Radar tweet and archive card."""

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


def short_text(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def first_title(rows: list[dict], fallback: str) -> str:
    if not rows:
        return fallback
    return str(rows[0].get("title") or fallback)


def format_tweet(data: dict) -> str:
    open_interest = money_short(float(data.get("open_interest", 0)))
    top_theme = short_text(
        data.get("hot_theme") or (data.get("top_themes") or [{}])[0].get("theme", "General"),
        38,
    )
    top_market = short_text(
        (data.get("hottest_market") or {}).get("title")
        or first_title(data.get("top_volume_markets") or data.get("top_markets") or [], "Market detail pending"),
        42,
    )
    top_oi_market = short_text(
        first_title(data.get("top_open_interest_markets") or data.get("top_markets") or [], top_market),
        42,
    )

    lines = [
        "What are people betting on today? 👀",
        "",
        "Prediction Market Radar via QVeris:",
        f"💰 Tracked OI: {open_interest}",
        f"🔥 Hottest market: {top_market}",
        f"📌 Hot theme: {top_theme}",
        f"📊 Top OI: {top_oi_market}",
        "",
        f"Live market data -> research-ready signals ⚡ {WEBSITE_URL}",
    ]
    tweet = "\n".join(lines)
    if len(tweet) > 280:
        lines = [
            "Prediction Market Radar via QVeris 👀",
            "",
            f"💰 Tracked OI: {open_interest}",
            f"🔥 Market: {short_text(top_market, 34)}",
            f"📌 Theme: {short_text(top_theme, 30)}",
            "",
            f"Signals from live market data: {WEBSITE_URL}",
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
        "contentType": "PREDICTION MARKET RADAR",
        "title": "Prediction Market Radar",
        "status": "ready",
        "tweet": tweet_text,
        "image": f"/posts/{public_image.name}",
        "dataSource": data.get("source", "QVeris API"),
        "dataUpdatedAt": data.get("updated_at", ""),
        "xPostId": None,
        "primaryLabel": "Hot theme",
        "primaryValue": str(data.get("hot_theme") or (data.get("top_themes") or [{}])[0].get("theme", "General"))[:32],
        "secondaryLabel": "Hottest market",
        "secondaryValue": str(
            (data.get("hottest_market") or (data.get("top_markets") or [{}])[0]).get("title", "Pending")
        )[:32],
        "topSymbol": "PM",
        "topChangePct": float(data.get("volume_change_pct", 0)),
        "polymarketPulse": data,
    }

    posts = [
        post
        for post in posts
        if post.get("id") != record["id"]
        and post.get("contentType") not in {"POLYMARKET PULSE", "PREDICTION MARKET", "WORLD CUP FINANCE"}
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

    print("==== Prediction Market Radar tweet preview ====")
    print(tweet_text)
    print(f"Characters: {len(tweet_text)}")
    print("Status: ready")


if __name__ == "__main__":
    main()
