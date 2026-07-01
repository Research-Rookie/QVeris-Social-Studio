"""Render the Financial News Signal card as a 1200x675 PNG."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = ROOT_DIR / "data" / "financial_news_signal.json"
TEMPLATE_FILE = SCRIPT_DIR / "templates" / "financial_news_signal_template.html"
LOGO_FILE = SCRIPT_DIR / "templates" / "logo-color.avif"
OUTPUT_DIR = ROOT_DIR / "images"
WIDTH, HEIGHT = 1200, 675


def get_logo_data_url() -> str:
    logo = base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii")
    return f"data:image/avif;base64,{logo}"


def short_text(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def ticker_rows(items: list[dict]) -> str:
    if not items:
        return '<li><span>Market</span><b>watching</b></li>'
    rows = []
    for item in items[:4]:
        ticker = str(item.get("ticker") or "Market")
        mentions = int(item.get("mentions") or 0)
        label = f"{mentions} mentions" if mentions else "watching"
        rows.append(f"<li><span>{html.escape(ticker)}</span><b>{html.escape(label)}</b></li>")
    return "\n".join(rows)


def headline_rows(articles: list[dict]) -> str:
    if not articles:
        return '<li><span class="headlineTitle">Headlines pending</span><span class="headlineMeta"><em>QVeris</em><b>Neutral</b></span></li>'
    rows = []
    for article in articles[:3]:
        title = short_text(article.get("title"), 88)
        source = short_text(article.get("source") or "Unknown", 22)
        sentiment = short_text(article.get("sentiment_label") or "Neutral", 20)
        rows.append(
            "<li>"
            f"<span class=\"headlineTitle\">{html.escape(title)}</span>"
            f"<span class=\"headlineMeta\"><em>{html.escape(source)}</em><b>{html.escape(sentiment)}</b></span>"
            "</li>"
        )
    return "\n".join(rows)


def render_html(data: dict) -> str:
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    return (
        template.replace("{{DATE}}", html.escape(str(data["date"])))
        .replace("{{ARTICLE_COUNT}}", html.escape(str(data.get("article_count", 0))))
        .replace("{{TOP_TICKER}}", html.escape(short_text(data.get("top_ticker", "Market"), 12)))
        .replace("{{SENTIMENT}}", html.escape(short_text(data.get("dominant_sentiment", "Neutral"), 18)))
        .replace("{{TOP_TOPIC}}", html.escape(short_text(data.get("top_topic", "Financial markets"), 28)))
        .replace("{{TAKEAWAY}}", html.escape(short_text(data.get("takeaway", ""), 180)))
        .replace("{{TOP_TICKERS}}", ticker_rows(data.get("top_tickers", [])))
        .replace("{{HEADLINES}}", headline_rows(data.get("articles", [])))
        .replace("{{LOGO}}", get_logo_data_url())
    )


def render_to_png(html_text: str, output_path: Path) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(
            viewport={"width": WIDTH, "height": HEIGHT},
            device_scale_factor=1,
        )
        page.set_content(html_text, wait_until="networkidle")
        page.screenshot(path=str(output_path))
        browser.close()


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8-sig"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dated_path = OUTPUT_DIR / f"financial_news_signal_{data['date']}.png"
    latest_path = OUTPUT_DIR / "financial_news_signal_latest.png"
    render_to_png(render_html(data), dated_path)
    latest_path.write_bytes(dated_path.read_bytes())
    print(f"Saved {dated_path}")
    print(f"Saved {latest_path}")


if __name__ == "__main__":
    main()
