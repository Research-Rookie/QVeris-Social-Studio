"""Render the News vs Price Reaction card as a 1200x675 PNG."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = ROOT_DIR / "data" / "news_vs_price_reaction.json"
TEMPLATE_FILE = SCRIPT_DIR / "templates" / "news_vs_price_reaction_template.html"
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


def money(value: object) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    if not number:
        return "Pending"
    return f"${number:,.2f}"


def signed_pct(value: object) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    return f"{number:+.2f}%"


def render_html(data: dict) -> str:
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    change_pct = float(data.get("change_pct") or 0)
    price_class = "positive" if change_pct >= 0 else "negative"
    return (
        template.replace("{{DATE}}", html.escape(str(data["date"])))
        .replace("{{SYMBOL}}", html.escape(short_text(data.get("symbol", "MARKET"), 8)))
        .replace("{{TOP_THEME}}", html.escape(short_text(data.get("top_theme", "Market"), 24)))
        .replace("{{NEWS_TONE}}", html.escape(short_text(data.get("news_tone", "Neutral"), 22)))
        .replace("{{CHANGE_PCT}}", html.escape(signed_pct(data.get("change_pct", 0))))
        .replace("{{PRICE_CLASS}}", html.escape(price_class))
        .replace("{{HEADLINE}}", html.escape(short_text(data.get("headline", ""), 122)))
        .replace("{{REACTION_LABEL}}", html.escape(short_text(data.get("reaction_label", "Watching"), 34)))
        .replace("{{TAKEAWAY}}", html.escape(short_text(data.get("takeaway", ""), 180)))
        .replace("{{PRICE}}", html.escape(money(data.get("price", 0))))
        .replace("{{HEADLINE_SOURCE}}", html.escape(short_text(data.get("headline_source", "QVeris"), 24)))
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
    dated_path = OUTPUT_DIR / f"news_vs_price_reaction_{data['date']}.png"
    latest_path = OUTPUT_DIR / "news_vs_price_reaction_latest.png"
    render_to_png(render_html(data), dated_path)
    latest_path.write_bytes(dated_path.read_bytes())
    print(f"Saved {dated_path}")
    print(f"Saved {latest_path}")


if __name__ == "__main__":
    main()
