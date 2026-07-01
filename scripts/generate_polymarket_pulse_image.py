"""Render the Prediction Market Radar card as a 1200x675 PNG."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = ROOT_DIR / "data" / "polymarket_pulse.json"
TEMPLATE_FILE = SCRIPT_DIR / "templates" / "polymarket_pulse_template.html"
LOGO_FILE = SCRIPT_DIR / "templates" / "logo-color.avif"
OUTPUT_DIR = ROOT_DIR / "images"
WIDTH, HEIGHT = 1200, 675


def get_logo_data_url() -> str:
    logo = base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii")
    return f"data:image/avif;base64,{logo}"


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


def signed_pct(value: float) -> str:
    return f"{value:+.1f}%"


def series_bars(series: list[dict]) -> str:
    rows = series[-7:]
    max_volume = max([float(row.get("volume", 0)) for row in rows] or [1])
    bars = []
    for row in rows:
        volume = float(row.get("volume", 0))
        height = max(8, int(volume / max_volume * 120)) if max_volume else 8
        label = str(row.get("date") or "")[-5:] or "day"
        bars.append(
            f"""
            <div class="barItem">
              <div class="barValue">{html.escape(money_short(volume))}</div>
              <div class="barColumn" style="height:{height}px"></div>
              <div class="barLabel">{html.escape(label)}</div>
            </div>
            """
        )
    return "\n".join(bars)


def market_rows_html(markets: list[dict], metric: str = "rank_value") -> str:
    if not markets:
        return '<li><span>Market detail</span><b>Not returned</b></li>'
    rows = []
    for market in markets[:3]:
        activity = float(
            market.get(metric)
            or market.get("rank_value")
            or market.get("activity")
            or market.get("open_interest")
            or market.get("volume")
            or 0
        )
        rows.append(
            f"<li><span>{html.escape(str(market.get('title', 'Market')))}</span>"
            f"<b>{html.escape(money_short(activity))}</b></li>"
        )
    return "\n".join(rows)


def theme_rows_html(themes: list[dict]) -> str:
    if not themes:
        return '<li><span>Theme detail</span><b>Not returned</b></li>'
    rows = []
    for theme in themes[:3]:
        rows.append(
            f"<li><span>{html.escape(str(theme.get('theme', 'General')))}</span>"
            f"<b>{html.escape(money_short(float(theme.get('activity', 0))))}</b></li>"
        )
    return "\n".join(rows)


def render_html(data: dict) -> str:
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    change = float(data.get("volume_change_pct", 0))
    change_class = "positive" if change >= 0 else "negative"
    top_theme = data.get("hot_theme") or (data.get("top_themes") or [{}])[0].get("theme", "General")
    top_market = (
        (data.get("hottest_market") or {}).get("title")
        or (data.get("top_markets") or [{}])[0].get("title", "Market detail pending")
    )
    open_interest = float(data.get("open_interest", 0))
    headline_value = open_interest or float(data.get("current_volume", 0))
    activity_label = "Radar" if open_interest else str(data.get("activity_label", "Stable"))
    takeaway = str(data.get("insight") or data.get("takeaway") or "")
    top_volume_markets = data.get("top_volume_markets") or data.get("top_markets", [])
    top_open_interest_markets = data.get("top_open_interest_markets") or data.get("top_markets", [])
    return (
        template.replace("{{DATE}}", html.escape(data["date"]))
        .replace("{{VOLUME}}", html.escape(money_short(headline_value)))
        .replace("{{VOLUME_CHANGE}}", html.escape(signed_pct(change)))
        .replace("{{CHANGE_CLASS}}", change_class)
        .replace("{{ACTIVITY_LABEL}}", html.escape(activity_label))
        .replace("{{TOP_THEME}}", html.escape(str(top_theme)))
        .replace("{{TOP_MARKET}}", html.escape(str(top_market)))
        .replace("{{OPEN_INTEREST}}", html.escape(money_short(open_interest)))
        .replace("{{TAKEAWAY}}", html.escape(takeaway))
        .replace("{{BARS}}", series_bars(data.get("volume_series", [])))
        .replace("{{TOP_THEMES}}", theme_rows_html(data.get("top_themes", [])))
        .replace("{{TOP_VOLUME_MARKETS}}", market_rows_html(top_volume_markets, "volume"))
        .replace("{{TOP_OPEN_INTEREST_MARKETS}}", market_rows_html(top_open_interest_markets, "open_interest"))
        .replace("{{TOP_MARKETS}}", market_rows_html(data.get("top_markets", [])))
        .replace("{{SOURCE}}", html.escape(data.get("source", "QVeris API")))
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
    dated_path = OUTPUT_DIR / f"polymarket_pulse_{data['date']}.png"
    latest_path = OUTPUT_DIR / "polymarket_pulse_latest.png"
    render_to_png(render_html(data), dated_path)
    latest_path.write_bytes(dated_path.read_bytes())
    print(f"Saved {dated_path}")
    print(f"Saved {latest_path}")


if __name__ == "__main__":
    main()
