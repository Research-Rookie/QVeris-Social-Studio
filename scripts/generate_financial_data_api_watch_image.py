"""Render the Financial Data API Watch card as a 1200x675 PNG."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = ROOT_DIR / "data" / "financial_data_api_watch.json"
TEMPLATE_FILE = SCRIPT_DIR / "templates" / "financial_data_api_watch_template.html"
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


def pct(value: float) -> str:
    return f"{value:.1f}%"


def money_short(value: float) -> str:
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.1f}T"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    return f"${value:.0f}"


def capability_rows(items: list[str]) -> str:
    return "\n".join(
        f"<li><span>{html.escape(item)}</span><b>API</b></li>"
        for item in items[:5]
    )


def retrieved_rows(items: list[dict]) -> str:
    return "\n".join(
        f"<li><span>{html.escape(str(item.get('label', 'Signal')))}</span>"
        f"<b>{html.escape(short_text(item.get('value', ''), 30))}</b></li>"
        for item in items[:4]
    )


def metric_cards(companies: list[dict]) -> str:
    cards = []
    for company in companies[:2]:
        cards.append(
            "<div class=\"metric\">"
            f"<span>${html.escape(company['symbol'])} FCF Yield</span>"
            f"<strong>{html.escape(pct(float(company.get('latest_fcf_yield', 0))))}</strong>"
            f"<span>Market cap {html.escape(money_short(float(company.get('market_cap', 0))))}</span>"
            "</div>"
        )
    return "\n".join(cards)


def render_html(data: dict) -> str:
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    news = data.get("news") or {}
    news_signal = f"{news.get('top_ticker', 'Market')} / {news.get('tone', 'Neutral')}"
    return (
        template.replace("{{DATE}}", html.escape(str(data["date"])))
        .replace("{{SCENARIO}}", html.escape(str(data.get("scenario", "Financial data workflow"))))
        .replace("{{AGENT_TASK}}", html.escape(short_text(data.get("agent_task", ""), 105)))
        .replace("{{CAPABILITIES}}", capability_rows(data.get("capabilities", [])))
        .replace("{{METRICS}}", metric_cards(data.get("companies", [])))
        .replace("{{RETRIEVED}}", retrieved_rows(data.get("retrieved", [])))
        .replace("{{NEWS_SIGNAL}}", html.escape(short_text(news_signal, 42)))
        .replace("{{TAKEAWAY}}", html.escape(short_text(data.get("takeaway", ""), 180)))
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
    dated_path = OUTPUT_DIR / f"financial_data_api_watch_{data['date']}.png"
    latest_path = OUTPUT_DIR / "financial_data_api_watch_latest.png"
    render_to_png(render_html(data), dated_path)
    latest_path.write_bytes(dated_path.read_bytes())
    print(f"Saved {dated_path}")
    print(f"Saved {latest_path}")


if __name__ == "__main__":
    main()
