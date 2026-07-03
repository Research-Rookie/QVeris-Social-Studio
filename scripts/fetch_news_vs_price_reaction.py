"""Build a News vs Price Reaction signal from QVeris news and quote data."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from qveris_finance import as_float, execute_best_tool, walk_dicts


ROOT_DIR = Path(__file__).resolve().parent.parent
NEWS_FILE = ROOT_DIR / "data" / "financial_news_signal.json"
OUTPUT_FILE = ROOT_DIR / "data" / "news_vs_price_reaction.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")
SESSION_ID = "qveris-social-studio-news-vs-price"
QUOTE_TOOL_ID = os.environ.get("QVERIS_STOCK_QUOTE_TOOL_ID", "")


def key_norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def value_by_names(item: dict[str, Any], names: list[str]) -> Any:
    normalized = {key_norm(str(key)): val for key, val in item.items()}
    for name in names:
        target = key_norm(name)
        if target in normalized:
            return normalized[target]
    return None


def clean_text(value: Any, limit: int = 140) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def display_label(value: Any) -> str:
    text = " ".join(str(value or "").replace("_", " ").replace("-", " ").split())
    return text.title() if text else ""


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Missing required input file: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def choose_ticker(news: dict[str, Any]) -> str:
    candidates = []
    if news.get("top_ticker"):
        candidates.append(str(news["top_ticker"]).upper())
    for item in news.get("top_tickers") or []:
        ticker = str(item.get("ticker") or "").upper()
        if ticker:
            candidates.append(ticker)
    for article in news.get("signal_articles") or news.get("articles") or []:
        candidates.extend(str(ticker).upper() for ticker in article.get("tickers") or [])

    for ticker in candidates:
        ticker = ticker.replace("$", "").strip()
        if re.fullmatch(r"[A-Z][A-Z0-9.]{0,5}", ticker) and ticker not in {"MARKET"}:
            return ticker
    return "NVDA"


def parse_quote(payload: dict[str, Any], symbol: str) -> dict[str, Any]:
    candidates = []
    for item in walk_dicts(payload):
        item_symbol = str(value_by_names(item, ["symbol", "ticker"]) or "").replace("$", "").upper()
        has_symbol = not item_symbol or item_symbol == symbol
        price = as_float(value_by_names(item, ["price", "lastPrice", "latestPrice", "currentPrice", "close", "regularMarketPrice", "05. price"]))
        change_pct = as_float(
            value_by_names(
                item,
                [
                    "changePercent",
                    "changePercentage",
                    "changesPercentage",
                    "percentChange",
                    "regularMarketChangePercent",
                    "10. change percent",
                ],
            )
        )
        change_amount = as_float(value_by_names(item, ["change", "changeAmount", "regularMarketChange", "09. change"]))
        volume = int(as_float(value_by_names(item, ["volume", "regularMarketVolume", "tradingVolume", "06. volume"])))
        if has_symbol and (price or change_pct or change_amount):
            candidates.append(
                {
                    "symbol": symbol,
                    "price": price,
                    "change_pct": change_pct,
                    "change_amount": change_amount,
                    "volume": volume,
                    "raw_source": "QVeris quote",
                }
            )
    if candidates:
        candidates.sort(key=lambda row: (bool(row["price"]), bool(row["change_pct"])), reverse=True)
        return candidates[0]
    raise RuntimeError(f"Could not parse quote data for {symbol}: {payload}")


def fetch_quote(symbol: str) -> tuple[dict[str, Any], str | None]:
    query = (
        f"US stock quote for {symbol} with latest price, change percentage, "
        "change amount, and volume"
    )
    try:
        payload = execute_best_tool(
            query,
            SESSION_ID,
            {
                "symbol": symbol,
                "ticker": symbol,
                "function": "GLOBAL_QUOTE",
                "market": "US",
            },
            configured_tool_id=QUOTE_TOOL_ID,
            max_response_size=65536,
        )
        return parse_quote(payload, symbol), None
    except Exception as error:
        return {
            "symbol": symbol,
            "price": 0.0,
            "change_pct": 0.0,
            "change_amount": 0.0,
            "volume": 0,
            "raw_source": "Price pending",
        }, str(error)


def sentiment_direction(sentiment: str) -> int:
    label = sentiment.lower()
    if "bullish" in label:
        return 1
    if "bearish" in label:
        return -1
    return 0


def classify_reaction(sentiment: str, change_pct: float, price_error: str | None) -> tuple[str, str]:
    if price_error:
        return "Price pending", "News signal is ready; price reaction will update once the quote tool returns data."
    news_dir = sentiment_direction(sentiment)
    price_dir = 1 if change_pct > 0.2 else -1 if change_pct < -0.2 else 0
    if news_dir > 0 and price_dir > 0:
        return "News confirmed", "Bullish news and positive price action are moving in the same direction."
    if news_dir > 0 and price_dir < 0:
        return "Market not buying it", "News tone is positive, but price action is negative. Expectations may already be priced in."
    if news_dir < 0 and price_dir > 0:
        return "Bad news absorbed", "Negative news with positive price action suggests the market may have looked through the headline."
    if news_dir < 0 and price_dir < 0:
        return "Pressure confirmed", "Negative news and falling price action are reinforcing each other."
    if news_dir == 0 and price_dir > 0:
        return "Price leads news", "News tone is neutral, but price action is positive."
    if news_dir == 0 and price_dir < 0:
        return "Price weakens", "News tone is neutral, but price action is negative."
    return "Muted reaction", "News tone and price action are both relatively muted."


def main() -> dict[str, Any]:
    news = load_json(NEWS_FILE)
    symbol = choose_ticker(news)
    quote, price_error = fetch_quote(symbol)
    top_article = (news.get("signal_articles") or news.get("articles") or [{}])[0]
    tone = display_label(news.get("dominant_sentiment") or "Neutral")
    reaction_label, takeaway = classify_reaction(tone, float(quote.get("change_pct") or 0), price_error)

    now = datetime.now(timezone.utc)
    run_now = datetime.now(RUN_TIMEZONE)
    output = {
        "updated_at": now.isoformat(),
        "date": run_now.strftime("%Y-%m-%d"),
        "run_timezone": "Asia/Shanghai",
        "source": "QVeris API via market news sentiment and stock quote",
        "title": "News vs Price Reaction",
        "symbol": symbol,
        "news_tone": tone,
        "top_theme": display_label(news.get("top_topic") or "Financial Markets"),
        "headline": clean_text(top_article.get("title") or news.get("top_story") or "Market headline pending", 132),
        "headline_source": clean_text(top_article.get("source") or "QVeris", 36),
        "price": quote.get("price", 0.0),
        "change_pct": quote.get("change_pct", 0.0),
        "change_amount": quote.get("change_amount", 0.0),
        "volume": quote.get("volume", 0),
        "reaction_label": reaction_label,
        "takeaway": takeaway,
        "price_error": price_error,
        "news": {
            "article_count": news.get("article_count", 0),
            "top_tickers": news.get("top_tickers", [])[:5],
            "sentiment_counts": news.get("sentiment_counts", []),
        },
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {OUTPUT_FILE}")
    print(f"{symbol}: {tone} news, {quote.get('change_pct', 0):+.2f}% price reaction")
    if price_error:
        print(f"Price warning: {price_error}")
    return output


if __name__ == "__main__":
    main()
