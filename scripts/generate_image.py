"""Render the daily Top 5 card as a 1200x675 PNG."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = ROOT_DIR / "data" / "rankings.json"
TEMPLATE_FILE = SCRIPT_DIR / "templates" / "top5_template.html"
LOGO_FILE = SCRIPT_DIR / "templates" / "logo-color.avif"
OUTPUT_DIR = ROOT_DIR / "images"
WIDTH, HEIGHT = 1200, 675


def get_logo_data_url() -> str:
    logo = base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii")
    return f"data:image/avif;base64,{logo}"


def build_row_html(stock: dict, rank: int) -> str:
    is_up = stock["change_pct"] >= 0
    pct_class = "up" if is_up else "down"
    arrow = "UP" if is_up else "DOWN"
    row_class = "row first" if rank == 1 else "row"

    return f"""
    <div class="{row_class}">
      <div class="left">
        <div class="rank">#{rank}</div>
        <div class="symbol">${stock['symbol']}</div>
      </div>
      <div class="right">
        <div class="price">${stock['price']:.2f}</div>
        <div class="pct {pct_class}">{arrow} {stock['change_pct']:+.2f}%</div>
      </div>
    </div>
    """


def render_html(data: dict) -> str:
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    rows = "\n".join(
        build_row_html(stock, rank)
        for rank, stock in enumerate(data["top5"], 1)
    )
    return (
        template.replace("{{DATE}}", data["date"])
        .replace("{{ROWS}}", rows)
        .replace("{{LOGO}}", get_logo_data_url())
    )


def render_to_png(html: str, output_path: Path) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(
            viewport={"width": WIDTH, "height": HEIGHT},
            device_scale_factor=1,
        )
        page.set_content(html, wait_until="networkidle")
        page.screenshot(path=str(output_path))
        browser.close()


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    html = render_html(data)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dated_path = OUTPUT_DIR / f"top5_{data['date']}.png"
    latest_path = OUTPUT_DIR / "latest.png"

    render_to_png(html, dated_path)
    latest_path.write_bytes(dated_path.read_bytes())

    print(f"Saved {dated_path}")
    print(f"Saved {latest_path}")


if __name__ == "__main__":
    main()
