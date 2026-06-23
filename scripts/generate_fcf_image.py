"""Render the FCF yield comparison card as a 1200x675 PNG."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = ROOT_DIR / "data" / "fcf_yield.json"
TEMPLATE_FILE = SCRIPT_DIR / "templates" / "fcf_yield_template.html"
LOGO_FILE = SCRIPT_DIR / "templates" / "logo-color.avif"
OUTPUT_DIR = ROOT_DIR / "images"
WIDTH, HEIGHT = 1200, 675
COLORS = ["#4ea3ff", "#ff5a4f"]


def get_logo_data_url() -> str:
    logo = base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii")
    return f"data:image/avif;base64,{logo}"


def money_billions(value: float) -> str:
    return f"${value / 1_000_000_000:.1f}B"


def pct(value: float) -> str:
    return f"{value:.1f}%"


def build_metric_html(companies: list[dict]) -> str:
    cards = []
    for index, company in enumerate(companies):
        color = COLORS[index % len(COLORS)]
        cards.append(
            f"""
            <div class="metric" style="--accent:{color}">
              <div class="metric-top">
                <span class="ticker">${html.escape(company['symbol'])}</span>
                <span class="yield">{pct(company['latest_fcf_yield'])}</span>
              </div>
              <div class="name">{html.escape(company['name'])}</div>
              <div class="sub">
                TTM FCF {money_billions(company['latest_ttm_fcf'])}
                · Market cap {money_billions(company['market_cap'])}
              </div>
            </div>
            """
        )
    return "\n".join(cards)


def point_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    start = f"M {points[0][0]:.1f} {points[0][1]:.1f}"
    rest = " ".join(f"L {x:.1f} {y:.1f}" for x, y in points[1:])
    return f"{start} {rest}"


def build_chart_svg(companies: list[dict]) -> str:
    chart_width = 940
    chart_height = 330
    pad_left = 58
    pad_right = 24
    pad_top = 24
    pad_bottom = 42
    inner_width = chart_width - pad_left - pad_right
    inner_height = chart_height - pad_top - pad_bottom

    series = [list(reversed(company["history"])) for company in companies]
    values = [
        item["fcf_yield"]
        for company_history in series
        for item in company_history
    ]
    min_value = min(values)
    max_value = max(values)
    if min_value == max_value:
        min_value -= 1
        max_value += 1
    padding = (max_value - min_value) * 0.16
    min_y = min(0, min_value - padding)
    max_y = max_value + padding

    def x_for(index: int, count: int) -> float:
        if count <= 1:
            return pad_left
        return pad_left + inner_width * index / (count - 1)

    def y_for(value: float) -> float:
        return pad_top + inner_height * (max_y - value) / (max_y - min_y)

    grid = []
    for step in range(5):
        value = min_y + (max_y - min_y) * step / 4
        y = y_for(value)
        grid.append(
            f'<line x1="{pad_left}" y1="{y:.1f}" x2="{chart_width - pad_right}" y2="{y:.1f}" />'
        )
        grid.append(
            f'<text x="8" y="{y + 4:.1f}">{value:.0f}%</text>'
        )

    paths = []
    labels = []
    for company_index, company in enumerate(companies):
        history = list(reversed(company["history"]))
        color = COLORS[company_index % len(COLORS)]
        points = [
            (x_for(index, len(history)), y_for(item["fcf_yield"]))
            for index, item in enumerate(history)
        ]
        paths.append(
            f'<path d="{point_path(points)}" stroke="{color}" />'
        )
        for x, y in points[-1:]:
            labels.append(
                f'<text class="end-label" x="{x + 8:.1f}" y="{y + 4:.1f}" fill="{color}">'
                f'{company["symbol"]} {company["latest_fcf_yield"]:.1f}%</text>'
            )

    dates = series[0] if series else []
    date_labels = []
    if dates:
        for index in [0, max(0, len(dates) // 2), len(dates) - 1]:
            item = dates[index]
            date_labels.append(
                f'<text class="date-label" x="{x_for(index, len(dates)):.1f}" '
                f'y="{chart_height - 12}">{html.escape(item["date"][:7])}</text>'
            )

    legend = []
    for company_index, company in enumerate(companies):
        color = COLORS[company_index % len(COLORS)]
        legend.append(
            f'<span><i style="background:{color}"></i>${html.escape(company["symbol"])}</span>'
        )

    return f"""
      <svg viewBox="0 0 {chart_width} {chart_height}" class="chart" aria-label="FCF yield history">
        <g class="grid">{"".join(grid)}</g>
        <line class="axis" x1="{pad_left}" y1="{chart_height - pad_bottom}" x2="{chart_width - pad_right}" y2="{chart_height - pad_bottom}" />
        <g class="lines">{"".join(paths)}</g>
        <g class="labels">{"".join(labels)}{"".join(date_labels)}</g>
      </svg>
      <div class="legend">{"".join(legend)}</div>
    """


def render_html(data: dict) -> str:
    companies = data["companies"]
    title = f"{companies[0]['symbol']} vs {companies[1]['symbol']} FCF Yield"
    subtitle = "TTM free cash flow divided by current market capitalization"
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    return (
        template.replace("{{TITLE}}", html.escape(title))
        .replace("{{SUBTITLE}}", html.escape(subtitle))
        .replace("{{DATE}}", data["date"])
        .replace("{{METRICS}}", build_metric_html(companies))
        .replace("{{CHART}}", build_chart_svg(companies))
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
    html_text = render_html(data)
    symbols = "_".join(company["symbol"] for company in data["companies"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dated_path = OUTPUT_DIR / f"fcf_yield_{symbols}_{data['date']}.png"
    latest_path = OUTPUT_DIR / "fcf_yield_latest.png"

    render_to_png(html_text, dated_path)
    latest_path.write_bytes(dated_path.read_bytes())

    print(f"Saved {dated_path}")
    print(f"Saved {latest_path}")


if __name__ == "__main__":
    main()
