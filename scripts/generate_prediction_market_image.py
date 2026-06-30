"""Render the prediction-market pulse card as a 1200x675 PNG."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = ROOT_DIR / "data" / "prediction_markets.json"
TEMPLATE_FILE = SCRIPT_DIR / "templates" / "prediction_market_template.html"
LOGO_FILE = SCRIPT_DIR / "templates" / "logo-color.avif"
OUTPUT_DIR = ROOT_DIR / "images"
WIDTH, HEIGHT = 1200, 675


def get_logo_data_url() -> str:
    logo = base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii")
    return f"data:image/avif;base64,{logo}"


def pct(value: float) -> str:
    return f"{value:.1f}%"


def pts(value: float) -> str:
    return f"{value:+.1f} pts"


def money_short(value: float) -> str:
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    if value > 0:
        return f"${value:.0f}"
    return "n/a"


def market_html(market: dict) -> str:
    probability = float(market.get("probability", 0))
    change = float(market.get("probability_change", 0))
    move_class = "up" if change >= 0 else "down"
    width = max(4, min(100, probability))
    has_probability = bool(market.get("has_probability", True))
    probability_label = pct(probability) if has_probability else "Watching"
    move_label = pts(change) if has_probability or change else "active"
    category = market.get("category") or "Prediction market"
    volume = float(market.get("volume", 0))
    liquidity = float(market.get("liquidity", 0))
    return f"""
      <article class="market">
        <div class="market-top">
          <div class="title">{html.escape(market.get('title', 'Prediction market'))}</div>
          <div class="prob">{html.escape(probability_label)}</div>
        </div>
        <div class="meta">
          <span class="pill {move_class}">{html.escape(move_label)}</span>
          <span class="pill">{html.escape(str(category))}</span>
          <span class="pill">Vol {money_short(volume)}</span>
          <span class="pill">Liq {money_short(liquidity)}</span>
        </div>
        <div class="bar-wrap"><div class="bar" style="width:{width:.1f}%"></div></div>
      </article>
    """


def render_html(data: dict) -> str:
    markets = data.get("markets", [])[:6]
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    return (
        template.replace("{{DATE}}", html.escape(data["date"]))
        .replace("{{MARKETS}}", "\n".join(market_html(market) for market in markets))
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
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dated_path = OUTPUT_DIR / f"prediction_market_{data['date']}.png"
    latest_path = OUTPUT_DIR / "prediction_market_latest.png"
    render_to_png(render_html(data), dated_path)
    latest_path.write_bytes(dated_path.read_bytes())
    print(f"Saved {dated_path}")
    print(f"Saved {latest_path}")


if __name__ == "__main__":
    main()
