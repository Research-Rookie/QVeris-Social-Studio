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
        "insider trading activity",
        "reported an \"other\" transaction",
        "shares sold",
        "shares acquired",
    ]
    return any(term in text for term in noise_terms)


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
    articles.sort(key=lambda item: item.get("published_at") or "", reverse=True)
    articles.sort(key=is_noise_article)
    return articles[:50]


def fetch_news() -> dict[str, Any]:
    parameter_sets = [
        {"function": "NEWS_SENTIMENT", "topics": "financial_markets", "sort": "LATEST", "limit": 50},
        {"function": "NEWS_SENTIMENT", "topics": "technology,financial_markets", "sort": "LATEST", "limit": 50},
        {"function": "NEWS_SENTIMENT", "sort": "LATEST", "limit": 50},
        {"function": "NEWS_SENTIMENT", "tickers": "AAPL,MSFT,NVDA,GOOGL,TSLA", "sort": "LATEST", "limit": 50},
    ]
    last_error = None
    for parameters in parameter_sets:
        try:
            print(f"Trying financial news parameters: {parameters}")
            return execute_tool(
                NEWS_TOOL_ID,
                SESSION_ID,
                parameters,
                max_response_size=65536,
            )
        except RuntimeError as error:
            last_error = error
            print(f"Financial news retry after {parameters}: {error}")
    raise RuntimeError(f"Could not fetch financial news: {last_error}")


def build_signal(articles: list[dict[str, Any]]) -> dict[str, Any]:
    signal_articles = [article for article in articles if not is_noise_article(article)]
    if not signal_articles:
        signal_articles = articles
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
    payload = fetch_news()
    articles = extract_articles(payload)
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
