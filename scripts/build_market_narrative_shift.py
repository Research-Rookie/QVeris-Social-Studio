"""Build a market narrative shift signal from QVeris financial-news archives."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT_DIR = Path(__file__).resolve().parent.parent
NEWS_FILE = ROOT_DIR / "data" / "financial_news_signal.json"
POSTS_FILE = ROOT_DIR / "data" / "posts.json"
OUTPUT_FILE = ROOT_DIR / "data" / "market_narrative_shift.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")

STOPWORDS = {
    "about", "after", "again", "against", "ahead", "analyst", "analysts", "and",
    "are", "around", "before", "being", "between", "billion", "company", "could",
    "from", "into", "latest", "market", "million", "more", "new", "news", "over",
    "corporation", "group", "holdings", "inc", "its", "nasdaq", "nyse", "price",
    "report", "shares", "stock", "than", "that", "the", "their", "this",
    "through", "today", "under", "with", "year", "years",
}

COMPANY_TERMS = {
    "AAPL": ["apple"],
    "ADBE": ["adobe"],
    "AMD": ["advanced micro devices", "amd"],
    "AMZN": ["amazon"],
    "GOOG": ["google", "alphabet"],
    "GOOGL": ["google", "alphabet"],
    "META": ["meta platforms", "meta"],
    "MSFT": ["microsoft"],
    "NFLX": ["netflix"],
    "NVDA": ["nvidia"],
    "PYPL": ["paypal"],
    "TSLA": ["tesla"],
}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def clean_text(value: Any, limit: int = 160) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def valid_symbol(value: Any) -> str:
    symbol = str(value or "").replace("$", "").strip().upper()
    return symbol if re.fullmatch(r"[A-Z]{1,5}", symbol) else ""


def signal_articles(news: dict[str, Any]) -> list[dict[str, Any]]:
    articles = news.get("signal_articles") or news.get("articles") or []
    return [
        article
        for article in articles
        if isinstance(article, dict)
        and not article.get("is_noise")
        and int(article.get("quality_score") or 0) >= 2
    ]


def words_for(articles: list[dict[str, Any]], symbol: str) -> Counter[str]:
    counter: Counter[str] = Counter()
    company_words = {
        word
        for term in COMPANY_TERMS.get(symbol, [])
        for word in re.findall(r"[a-z][a-z0-9-]{2,}", term.lower())
    }
    for article in articles:
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        for word in re.findall(r"[a-z][a-z0-9-]{2,}", text):
            normalized = word.strip("-")
            if normalized in STOPWORDS or normalized in company_words or normalized == symbol.lower() or normalized.isdigit():
                continue
            counter[normalized] += 1
    return counter


def snapshot(news: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    mentioned_articles = [
        article
        for article in signal_articles(news)
        if symbol in [valid_symbol(item) for item in article.get("tickers") or []]
    ]
    primary_articles = []
    for article in mentioned_articles:
        title = str(article.get("title") or "").lower()
        company_match = any(term in title for term in COMPANY_TERMS.get(symbol, []))
        ticker_match = re.search(rf"(?<![a-z])\$?{re.escape(symbol.lower())}(?![a-z])", title)
        if valid_symbol((article.get("tickers") or [""])[0]) == symbol or company_match or ticker_match:
            primary_articles.append(article)
    articles = primary_articles or mentioned_articles
    if not articles:
        return None

    topics: Counter[str] = Counter()
    sources: set[str] = set()
    sentiment_scores: list[float] = []
    for article in articles:
        topics.update(str(topic) for topic in article.get("topics") or [] if topic)
        sources.add(str(article.get("source") or "Unknown"))
        sentiment_scores.append(float(article.get("sentiment_score") or 0.0))

    keywords = words_for(articles, symbol)
    return {
        "date": str(news.get("date") or ""),
        "symbol": symbol,
        "article_count": len(articles),
        "source_count": len(sources),
        "sentiment_score": round(sum(sentiment_scores) / len(sentiment_scores), 4),
        "top_theme": topics.most_common(1)[0][0] if topics else "Financial Markets",
        "themes": [{"label": label, "count": count} for label, count in topics.most_common(5)],
        "keywords": [{"label": label, "count": count} for label, count in keywords.most_common(12)],
        "headline": clean_text(articles[0].get("title"), 132),
        "headline_source": clean_text(articles[0].get("source") or "QVeris", 36),
    }


def historical_news(posts: list[dict[str, Any]], current_date: str) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for post in posts:
        if str(post.get("date") or "") >= current_date:
            continue
        narrative = post.get("marketNarrativeShift")
        if isinstance(narrative, dict) and isinstance(narrative.get("current"), dict):
            history.append({"kind": "snapshot", "value": narrative["current"]})
        news = post.get("financialNewsSignal")
        if isinstance(news, dict):
            history.append({"kind": "news", "value": news})
    return history


def prior_snapshot(history: list[dict[str, Any]], symbol: str) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for entry in history:
        value = entry["value"]
        candidate = value if entry["kind"] == "snapshot" else snapshot(value, symbol)
        if candidate and candidate.get("symbol") == symbol:
            candidates.append(candidate)
    return max(candidates, key=lambda item: str(item.get("date") or ""), default=None)


def labels(items: list[dict[str, Any]]) -> Counter[str]:
    return Counter({str(item.get("label")): int(item.get("count") or 0) for item in items})


def delta_terms(current: dict[str, Any], previous: dict[str, Any] | None, field: str) -> tuple[list[str], list[str]]:
    current_counts = labels(current.get(field) or [])
    previous_counts = labels((previous or {}).get(field) or [])
    rising = sorted(current_counts, key=lambda key: (current_counts[key] - previous_counts[key], current_counts[key]), reverse=True)
    fading = sorted(previous_counts, key=lambda key: (previous_counts[key] - current_counts[key], previous_counts[key]), reverse=True)
    return rising[:3], [item for item in fading if previous_counts[item] > current_counts[item]][:3]


def classify_shift(current: dict[str, Any], previous: dict[str, Any] | None) -> tuple[str, float]:
    if not previous:
        return "Baseline building", 0.0
    delta = float(current["sentiment_score"]) - float(previous.get("sentiment_score") or 0.0)
    if delta >= 0.12:
        if float(current["sentiment_score"]) <= -0.15:
            return "Bearish pressure easing", delta
        return "Turning bullish", delta
    if delta <= -0.12:
        if float(current["sentiment_score"]) >= 0.15:
            return "Bullish momentum cooling", delta
        return "Turning bearish", delta
    if current.get("top_theme") != previous.get("top_theme"):
        return "Theme rotation", delta
    current_count = int(current.get("article_count") or 0)
    previous_count = max(int(previous.get("article_count") or 0), 1)
    if current_count >= previous_count * 1.5:
        return "Attention rising", delta
    if current_count * 1.5 <= previous_count:
        return "Attention cooling", delta
    return "Narrative steady", delta


def main() -> dict[str, Any]:
    news = load_json(NEWS_FILE, {})
    posts = load_json(POSTS_FILE, [])
    current_date = str(news.get("date") or datetime.now(RUN_TIMEZONE).strftime("%Y-%m-%d"))
    history = historical_news(posts, current_date)

    ticker_counts: Counter[str] = Counter()
    for article in signal_articles(news):
        ticker_counts.update(filter(None, (valid_symbol(item) for item in article.get("tickers") or [])))
    if not ticker_counts:
        raise RuntimeError("Financial News Signal contains no usable ticker mentions.")

    candidates: list[tuple[int, str, dict[str, Any], dict[str, Any] | None]] = []
    for symbol, mentions in ticker_counts.most_common(12):
        current = snapshot(news, symbol)
        if not current:
            continue
        previous = prior_snapshot(history, symbol)
        score = mentions * 10 + int(current.get("source_count") or 0) * 2 + (12 if previous else 0)
        candidates.append((score, symbol, current, previous))
    if not candidates:
        raise RuntimeError("Could not build a narrative snapshot for any ticker.")

    _, symbol, current, previous = max(candidates, key=lambda item: item[0])
    rising_themes, fading_themes = delta_terms(current, previous, "themes")
    emerging_keywords, fading_keywords = delta_terms(current, previous, "keywords")
    shift_label, sentiment_delta = classify_shift(current, previous)
    baseline_label = str(previous.get("date")) if previous else "Building"
    prior_theme = str(previous.get("top_theme") or "No baseline") if previous else "No baseline"

    if previous:
        takeaway = (
            f"{symbol}'s narrative is {shift_label.lower()}: sentiment moved "
            f"{sentiment_delta:+.2f}, while the leading theme shifted from {prior_theme} "
            f"to {current['top_theme']}."
        )
    else:
        takeaway = (
            f"{symbol} leads the current news set. This first snapshot establishes the baseline "
            "for the next narrative comparison."
        )

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "date": current_date,
        "run_timezone": "Asia/Shanghai",
        "source": "QVeris API via market news sentiment",
        "title": "Market Narrative Shift",
        "symbol": symbol,
        "shift_label": shift_label,
        "sentiment_delta": round(sentiment_delta, 4),
        "baseline_label": baseline_label,
        "current": current,
        "previous": previous,
        "emerging_themes": rising_themes,
        "fading_themes": fading_themes,
        "emerging_keywords": emerging_keywords,
        "fading_keywords": fading_keywords,
        "takeaway": takeaway,
        "selection_method": "Highest-quality ticker with current coverage; prior coverage receives a continuity boost.",
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {OUTPUT_FILE}")
    print(f"Ticker: {symbol}")
    print(f"Shift: {shift_label}")
    print(f"Baseline: {baseline_label}")
    return output


if __name__ == "__main__":
    main()
