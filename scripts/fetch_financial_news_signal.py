"""Fetch Financial News Signal data from QVeris."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from qveris_finance import as_float, execute_tool, walk_dicts


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT_DIR / "data" / "financial_news_signal.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")
SESSION_ID = "qveris-social-studio-financial-news-signal"
NEWS_TOOL_ID = os.environ.get(
    "QVERIS_FINANCIAL_NEWS_TOOL_ID",
    "alphavantage.news_sentiment.query.v1.7aca3c4a",
)
MAX_NEWS_CALLS = int(os.environ.get("QVERIS_FINANCIAL_NEWS_MAX_CALLS", "4"))


def value_by_any(item: dict[str, Any], names: list[str]) -> Any:
    normalized = {
        "".join(ch for ch in str(key).lower() if ch.isalnum()): value
        for key, value in item.items()
    }
    for name in names:
        key = "".join(ch for ch in name.lower() if ch.isalnum())
        if key in normalized:
            return normalized[key]
    return None


def parse_embedded_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        full_content_url = payload.get("full_content_file_url")
        if isinstance(full_content_url, str) and full_content_url.startswith(("http://", "https://")):
            try:
                with urlopen(full_content_url, timeout=60) as response:
                    return json.loads(response.read().decode("utf-8"))
            except Exception as error:
                print(f"Could not download QVeris full content: {error}")
        content = payload.get("truncated_content") or payload.get("content") or payload.get("data")
        if isinstance(content, str) and content.strip().startswith(("[", "{")):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return payload
    return payload


def clean_text(value: Any, limit: int = 140) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def display_label(value: Any) -> str:
    text = " ".join(str(value or "").replace("_", " ").replace("-", " ").split())
    return text.title() if text else ""


def is_noise_article(article: dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(article.get("title") or ""),
            str(article.get("summary") or ""),
            str(article.get("url") or ""),
        ]
    ).lower()
    noise_terms = [
        "form 4",
        "sec filing",
        "sec-filings",
        "insider",
        "insider trading activity",
        "reported an \"other\" transaction",
        "shares sold",
        "shares acquired",
        "registers shares",
        "registered shares",
        "ceo sells",
        "director sells",
        "sells shares",
        "exercising options",
        "10b5-1",
        "sepa line",
        "standby equity purchase",
        "shelf registration",
        "registered direct offering",
        "at-the-market offering",
        "warrant",
        "beneficial ownership",
        "shareholder alert",
        "class action",
        "deadline alert",
    ]
    return any(term in text for term in noise_terms)


def article_quality_score(article: dict[str, Any]) -> int:
    text = " ".join(
        [
            str(article.get("title") or ""),
            str(article.get("summary") or ""),
            str(article.get("source") or ""),
        ]
    ).lower()
    if is_noise_article(article):
        return -10

    high_signal_terms = [
        "earnings",
        "revenue",
        "profit",
        "guidance",
        "forecast",
        "outlook",
        "beats",
        "misses",
        "raises",
        "cuts",
        "acquisition",
        "merger",
        "deal",
        "partnership",
        "contract",
        "launches",
        "approval",
        "fda",
        "tariff",
        "inflation",
        "fed",
        "rates",
        "jobs",
        "oil",
        "ai",
        "chips",
        "semiconductor",
        "data center",
        "analyst",
        "upgrade",
        "downgrade",
        "market",
        "stocks",
        "etf",
        "bitcoin",
    ]
    weak_signal_terms = [
        "trading",
        "investors",
        "wall street",
        "nasdaq",
        "nyse",
        "pre-market",
        "premarket",
        "after-hours",
    ]
    score = 0
    score += sum(3 for term in high_signal_terms if term in text)
    score += sum(1 for term in weak_signal_terms if term in text)
    if article.get("summary"):
        score += 1
    if article.get("tickers"):
        score += 1
    if article.get("source") and str(article["source"]).lower() not in {"stock titan"}:
        score += 1
    return score


def normalize_sentiment(label: str, score: float) -> str:
    text = " ".join(str(label or "").replace("_", " ").split()).title()
    if text:
        return text
    if score >= 0.35:
        return "Bullish"
    if score >= 0.15:
        return "Somewhat Bullish"
    if score <= -0.35:
        return "Bearish"
    if score <= -0.15:
        return "Somewhat Bearish"
    return "Neutral"


def extract_tickers(item: dict[str, Any]) -> list[str]:
    tickers: list[str] = []
    raw = value_by_any(item, ["ticker", "tickers", "symbol", "symbols"])
    if isinstance(raw, str):
        tickers.extend(token.strip().upper() for token in raw.replace(";", ",").split(",") if token.strip())
    elif isinstance(raw, list):
        for token in raw:
            if isinstance(token, str):
                tickers.append(token.strip().upper())
            elif isinstance(token, dict):
                ticker = value_by_any(token, ["ticker", "symbol"])
                if ticker:
                    tickers.append(str(ticker).strip().upper())

    ticker_sentiment = value_by_any(item, ["ticker_sentiment", "tickerSentiment"])
    if isinstance(ticker_sentiment, list):
        for entry in ticker_sentiment:
            if isinstance(entry, dict):
                ticker = value_by_any(entry, ["ticker", "symbol"])
                if ticker:
                    tickers.append(str(ticker).strip().upper())

    cleaned = []
    for ticker in tickers:
        ticker = ticker.replace("$", "").strip()
        if ticker and ticker not in cleaned:
            cleaned.append(ticker)
    return cleaned[:8]


def extract_topics(item: dict[str, Any]) -> list[str]:
    topics: list[str] = []
    raw = value_by_any(item, ["topics", "topic", "category", "category_within_source"])
    if isinstance(raw, str):
        topics.extend(token.strip() for token in raw.replace(";", ",").split(",") if token.strip())
    elif isinstance(raw, list):
        for token in raw:
            if isinstance(token, str):
                topics.append(token.strip())
            elif isinstance(token, dict):
                topic = value_by_any(token, ["topic", "name", "label"])
                if topic:
                    topics.append(str(topic).strip())
    return [clean_text(display_label(topic), 38) for topic in topics if topic][:5]


def article_from_item(item: dict[str, Any]) -> dict[str, Any] | None:
    title = clean_text(value_by_any(item, ["title", "headline"]), 118)
    url = str(value_by_any(item, ["url", "link"]) or "")
    if not title or not url.startswith(("http://", "https://")):
        return None
    score = as_float(value_by_any(item, ["overall_sentiment_score", "sentiment_score", "score"]))
    label = normalize_sentiment(str(value_by_any(item, ["overall_sentiment_label", "sentiment_label", "sentiment"]) or ""), score)
    return {
        "title": title,
        "summary": clean_text(value_by_any(item, ["summary", "description", "abstract"]), 180),
        "url": url,
        "source": clean_text(value_by_any(item, ["source", "source_domain", "publisher"]), 36) or "Unknown",
        "published_at": str(value_by_any(item, ["time_published", "published_at", "publishedAt", "datetime", "date"]) or ""),
        "sentiment_score": score,
        "sentiment_label": label,
        "tickers": extract_tickers(item),
        "topics": extract_topics(item),
    }


def extract_articles(payload: Any) -> list[dict[str, Any]]:
    parsed = parse_embedded_payload(payload)
    articles: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in walk_dicts(parsed):
        article = article_from_item(item)
        if not article:
            continue
        identity = article["url"] or article["title"]
        if identity in seen:
            continue
        seen.add(identity)
        articles.append(article)
    for article in articles:
        article["quality_score"] = article_quality_score(article)
        article["is_noise"] = is_noise_article(article)
    articles.sort(key=lambda item: str(item.get("published_at") or ""), reverse=True)
    articles.sort(key=lambda item: (bool(item.get("is_noise")), -int(item.get("quality_score") or 0)))
    return articles[:50]


def fetch_news_payloads() -> list[dict[str, Any]]:
    parameter_sets = [
        {"function": "NEWS_SENTIMENT", "topics": "earnings", "sort": "LATEST", "limit": 50},
        {"function": "NEWS_SENTIMENT", "topics": "technology", "sort": "LATEST", "limit": 50},
        {"function": "NEWS_SENTIMENT", "topics": "economy_macro", "sort": "LATEST", "limit": 50},
        {"function": "NEWS_SENTIMENT", "topics": "financial_markets", "sort": "LATEST", "limit": 50},
        {"function": "NEWS_SENTIMENT", "tickers": "AAPL,MSFT,NVDA,GOOGL,TSLA", "sort": "LATEST", "limit": 50},
    ]
    payloads = []
    for parameters in parameter_sets:
        if len(payloads) >= MAX_NEWS_CALLS:
            break
        try:
            print(f"Trying financial news parameters: {parameters}")
            payload = execute_tool(
                NEWS_TOOL_ID,
                SESSION_ID,
                parameters,
                max_response_size=65536,
            )
            payloads.append(payload)
            current_articles = [
                article
                for saved_payload in payloads
                for article in extract_articles(saved_payload)
            ]
            high_quality_count = sum(
                1
                for article in dedupe_articles(current_articles)
                if not article.get("is_noise") and int(article.get("quality_score") or 0) >= 2
            )
            if high_quality_count >= 8:
                print(f"Collected {high_quality_count} high-quality news articles; stopping early.")
                break
        except RuntimeError as error:
            print(f"Financial news retry after {parameters}: {error}")
    if not payloads:
        raise RuntimeError("Could not fetch financial news from any configured QVeris parameter set.")
    return payloads


def dedupe_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped = []
    seen = set()
    for article in articles:
        identity = article.get("url") or article.get("title")
        if not identity or identity in seen:
            continue
        seen.add(identity)
        deduped.append(article)
    deduped.sort(key=lambda item: str(item.get("published_at") or ""), reverse=True)
    deduped.sort(key=lambda item: (bool(item.get("is_noise")), -int(item.get("quality_score") or 0)))
    return deduped[:50]


def build_signal(articles: list[dict[str, Any]]) -> dict[str, Any]:
    signal_articles = [
        article
        for article in articles
        if not article.get("is_noise") and int(article.get("quality_score") or 0) >= 2
    ]
    if len(signal_articles) < 3:
        signal_articles = [article for article in articles if not article.get("is_noise")]
    if len(signal_articles) < 3:
        signal_articles = articles[:10]
    ticker_counter: Counter[str] = Counter()
    topic_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()
    sentiment_counter: Counter[str] = Counter()
    for article in signal_articles:
        ticker_counter.update(article.get("tickers") or [])
        topic_counter.update(article.get("topics") or [])
        source_counter.update([article.get("source") or "Unknown"])
        sentiment_counter.update([article.get("sentiment_label") or "Neutral"])

    top_ticker = ticker_counter.most_common(1)[0][0] if ticker_counter else "Market"
    top_topic = topic_counter.most_common(1)[0][0] if topic_counter else "Financial markets"
    sentiment_label = sentiment_counter.most_common(1)[0][0] if sentiment_counter else "Neutral"
    top_story = signal_articles[0]["title"] if signal_articles else "Market headlines pending"
    takeaway = (
        f"News flow is centered on {top_topic}, with {top_ticker} appearing most often "
        f"and the headline tone mostly {sentiment_label.lower()}."
    )
    return {
        "article_count": len(articles),
        "top_ticker": top_ticker,
        "top_topic": top_topic,
        "dominant_sentiment": sentiment_label,
        "top_story": top_story,
        "signal_articles": signal_articles[:10],
        "top_tickers": [{"ticker": ticker, "mentions": count} for ticker, count in ticker_counter.most_common(5)],
        "top_topics": [{"topic": topic, "mentions": count} for topic, count in topic_counter.most_common(5)],
        "sentiment_counts": [{"label": label, "count": count} for label, count in sentiment_counter.most_common()],
        "top_sources": [{"source": source, "count": count} for source, count in source_counter.most_common(5)],
        "takeaway": takeaway,
    }


def main() -> dict[str, Any]:
    payloads = fetch_news_payloads()
    articles = dedupe_articles(
        [
            article
            for payload in payloads
            for article in extract_articles(payload)
        ]
    )
    if not articles:
        raise RuntimeError("QVeris returned no usable financial-news articles.")

    now = datetime.now(timezone.utc)
    run_now = datetime.now(RUN_TIMEZONE)
    signal = build_signal(articles)
    output = {
        "updated_at": now.isoformat(),
        "date": run_now.strftime("%Y-%m-%d"),
        "run_timezone": "Asia/Shanghai",
        "source": "QVeris API via market news sentiment",
        "title": "Financial News Signal",
        "articles": articles,
        **signal,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved {OUTPUT_FILE}")
    print(f"Articles: {len(articles)}")
    print(f"Top ticker: {signal['top_ticker']}")
    print(f"Dominant sentiment: {signal['dominant_sentiment']}")
    return output


if __name__ == "__main__":
    main()
