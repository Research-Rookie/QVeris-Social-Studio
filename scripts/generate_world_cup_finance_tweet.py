"""Generate one World Cup ETF tweet and website card per finished match."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "world_cup_finance.json"
POSTS_FILE = ROOT_DIR / "data" / "posts.json"
TWEET_PREVIEW_FILE = ROOT_DIR / "data" / "world_cup_finance_tweet_preview.txt"
SOURCE_IMAGE_DIR = ROOT_DIR / "images"
PUBLIC_POSTS_DIR = ROOT_DIR / "public" / "posts"
WEBSITE_URL = os.environ.get("WEBSITE_URL", "https://qveris.ai")


def pct(value: float) -> str:
    return f"{value:+.2f}%"


def safe_slug(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "match"


def match_slug(match: dict, date: str) -> str:
    return safe_slug(f"{date}-{match['id']}-{match['home']['team']}-{match['away']['team']}")


def winner_line(match: dict) -> str:
    home = match["home"]
    away = match["away"]
    if match.get("result") == "home_win":
        return f"{home['team']} beat {away['team']} {home['score']}-{away['score']}."
    if match.get("result") == "away_win":
        return f"{away['team']} beat {home['team']} {away['score']}-{home['score']}."
    return f"{home['team']} drew {away['team']} {home['score']}-{away['score']}."


def format_tweet(data: dict, match: dict) -> str:
    home = match["home"]
    away = match["away"]
    home_pct = pct(float(home["quote"].get("change_pct", 0)))
    away_pct = pct(float(away["quote"].get("change_pct", 0)))
    home_label = "proxy ETF" if home.get("is_proxy") else "ETF"
    away_label = "proxy ETF" if away.get("is_proxy") else "ETF"
    lines = [
        f"⚽ World Cup result: {match['label']}",
        "",
        "📊 Next-session ETF check:",
        f"${home['etf']} {home['country']} {home_label}: {home_pct}",
        f"${away['etf']} {away['country']} {away_label}: {away_pct}",
        "",
        "Not a causal claim. Just tracking how football attention and country ETFs move together.",
        "",
        f"Built with QVeris ⚡ {WEBSITE_URL}",
    ]
    tweet = "\n".join(lines)
    if len(tweet) > 280:
        lines = [
            f"⚽ {match['label']}",
            "",
            f"📊 Next-session ETF check: ${home['etf']} {home_pct} vs ${away['etf']} {away_pct}",
            "",
            "Not causal. A clean sports-attention x ETF tracker, built with QVeris.",
            WEBSITE_URL,
        ]
        tweet = "\n".join(lines)
    if len(tweet) > 280:
        raise RuntimeError(f"Tweet is {len(tweet)} characters; limit is 280")
    return tweet


def archive_post(data: dict, match: dict, tweet_text: str) -> None:
    PUBLIC_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = match_slug(match, data["date"])
    image_name = f"world_cup_etf_{slug}.png"
    source_image = SOURCE_IMAGE_DIR / image_name
    if not source_image.exists():
        raise RuntimeError(f"Missing generated image: {source_image}")
    public_image = PUBLIC_POSTS_DIR / image_name
    shutil.copy2(source_image, public_image)

    posts = []
    if POSTS_FILE.exists():
        posts = json.loads(POSTS_FILE.read_text(encoding="utf-8"))

    home = match["home"]
    away = match["away"]
    home_pct = float(home["quote"].get("change_pct", 0))
    away_pct = float(away["quote"].get("change_pct", 0))
    record = {
        "id": f"world-cup-etf-{slug}",
        "date": data["date"],
        "matchDate": data.get("match_date", data["date"]),
        "marketCheckDate": data.get("market_check_date", data["date"]),
        "runDate": data["date"],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "contentType": "WORLD CUP FINANCE",
        "title": f"{home['team']} vs {away['team']} Market Aftermath",
        "status": "ready",
        "tweet": tweet_text,
        "image": f"/posts/{public_image.name}",
        "dataSource": data.get("source", "QVeris API"),
        "dataUpdatedAt": data.get("updated_at", ""),
        "xPostId": None,
        "primaryLabel": f"${home['etf']} next-session move",
        "primaryValue": pct(home_pct),
        "secondaryLabel": f"${away['etf']} next-session move",
        "secondaryValue": pct(away_pct),
        "topSymbol": home["etf"] if abs(home_pct) >= abs(away_pct) else away["etf"],
        "topChangePct": home_pct if abs(home_pct) >= abs(away_pct) else away_pct,
        "worldCupFinance": {
            "date": data["date"],
            "matchDate": data.get("match_date", data["date"]),
            "marketCheckDate": data.get("market_check_date", data["date"]),
            "event": data.get("event"),
            "match": match,
            "source": data.get("source"),
        },
    }

    posts = [post for post in posts if post.get("id") != record["id"]]
    posts.append(record)
    posts.sort(key=lambda post: (post["date"], post.get("createdAt", "")), reverse=True)
    POSTS_FILE.write_text(
        json.dumps(posts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    matches = data.get("matches") or []
    if not matches:
        print("No finished mapped World Cup matches. Skipping tweet/archive generation.")
        return

    tweets = []
    for match in matches:
        tweet_text = format_tweet(data, match)
        archive_post(data, match, tweet_text)
        tweets.append(f"==== {match['label']} ====\n{tweet_text}\nCharacters: {len(tweet_text)}")

    TWEET_PREVIEW_FILE.write_text("\n\n".join(tweets), encoding="utf-8")
    print("==== World Cup ETF tweet previews ====")
    print("\n\n".join(tweets))
    print("Status: ready")


if __name__ == "__main__":
    main()
