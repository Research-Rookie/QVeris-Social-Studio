"""Generate the FCF yield comparison tweet and archive card."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "fcf_yield.json"
POSTS_FILE = ROOT_DIR / "data" / "posts.json"
TWEET_PREVIEW_FILE = ROOT_DIR / "data" / "fcf_tweet_preview.txt"
SOURCE_IMAGE = ROOT_DIR / "images" / "fcf_yield_latest.png"
PUBLIC_POSTS_DIR = ROOT_DIR / "public" / "posts"
WEBSITE_URL = os.environ.get("WEBSITE_URL", "https://qveris.ai")


def format_tweet(data: dict) -> str:
    companies = data["companies"]
    left, right = companies[0], companies[1]
    lines = [
        f"Which would you rather own at current prices, ${left['symbol']} or ${right['symbol']}?",
        "",
        f"{left['symbol']} FCF Yield: {left['latest_fcf_yield']:.1f}%",
        f"{right['symbol']} FCF Yield: {right['latest_fcf_yield']:.1f}%",
        "",
        f"${left['symbol']} ${right['symbol']}",
        "",
        f"More market data: {WEBSITE_URL}",
        "",
        "Information only. Not investment advice.",
    ]
    tweet = "\n".join(lines)
    if len(tweet) > 280:
        raise RuntimeError(f"Tweet is {len(tweet)} characters; limit is 280")
    return tweet


def archive_post(data: dict, tweet_text: str) -> None:
    PUBLIC_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    symbols = "_".join(company["symbol"] for company in data["companies"])
    public_image = PUBLIC_POSTS_DIR / f"fcf_yield_{symbols}_{data['date']}.png"
    shutil.copy2(SOURCE_IMAGE, public_image)

    posts = []
    if POSTS_FILE.exists():
        posts = json.loads(POSTS_FILE.read_text(encoding="utf-8"))

    left, right = data["companies"]
    record = {
        "id": f"fcf-yield-{symbols.lower().replace('_', '-')}-{data['date']}",
        "date": data["date"],
        "runDate": data["date"],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "contentType": "FCF YIELD",
        "title": f"{left['symbol']} vs {right['symbol']} FCF Yield",
        "status": "ready",
        "tweet": tweet_text,
        "image": f"/posts/{public_image.name}",
        "dataSource": data.get("source", "Financial Modeling Prep"),
        "dataUpdatedAt": data.get("updated_at", ""),
        "xPostId": None,
        "primaryLabel": f"${left['symbol']} FCF Yield",
        "primaryValue": f"{left['latest_fcf_yield']:.1f}%",
        "secondaryLabel": f"${right['symbol']} FCF Yield",
        "secondaryValue": f"{right['latest_fcf_yield']:.1f}%",
        "topSymbol": left["symbol"],
        "topChangePct": left["latest_fcf_yield"],
        "comparison": data,
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

    print("==== FCF tweet preview ====")
    print(tweet_text)
    print(f"Characters: {len(tweet_text)}")
    print("Status: ready")


if __name__ == "__main__":
    main()
