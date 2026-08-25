"""Render a compact, deterministic SVG portfolio dashboard."""

from __future__ import annotations

from html import escape
from pathlib import Path

import numpy as np
import pandas as pd


def _text(x: float, y: float, value: str, css_class: str, anchor: str = "start") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{css_class}" '
        f'text-anchor="{anchor}">{escape(value)}</text>'
    )


def _scale(value: float, low: float, high: float, start: float, end: float) -> float:
    return start + (value - low) / (high - low) * (end - start)


def render_dashboard(
    *,
    state_path: Path,
    coefficients_path: Path,
    diagnostics_path: Path,
    correlations_path: Path,
    output_path: Path,
) -> Path:
    states = pd.read_csv(state_path)
    coefficients = pd.read_csv(coefficients_path).set_index("term")
    diagnostics = pd.read_csv(diagnostics_path).iloc[0]
    correlations = pd.read_csv(correlations_path, index_col=0)
    sample = states.loc[states["eligible_primary_model"]].copy()

    width, height = 1400, 900
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        """<style>
        .title{font:700 30px Inter,Arial,sans-serif;fill:#f8fafc}.subtitle{font:400 14px Inter,Arial,sans-serif;fill:#b9c7da}
        .panel-title{font:700 17px Inter,Arial,sans-serif;fill:#172033}.panel-sub{font:400 12px Inter,Arial,sans-serif;fill:#64748b}
        .kpi{font:700 25px Inter,Arial,sans-serif;fill:#0f172a}.kpi-label{font:600 11px Inter,Arial,sans-serif;fill:#64748b;letter-spacing:.6px}
        .axis{font:400 10px Inter,Arial,sans-serif;fill:#64748b}.small{font:400 11px Inter,Arial,sans-serif;fill:#475569}
        .label{font:600 11px Inter,Arial,sans-serif;fill:#334155}.value{font:700 12px Inter,Arial,sans-serif;fill:#0f172a}
        .note{font:400 11px Inter,Arial,sans-serif;fill:#64748b}.takeaway{font:500 13px Inter,Arial,sans-serif;fill:#25324a}
        </style>""",
        '<rect width="1400" height="900" fill="#f3f6fa"/>',
        '<rect width="1400" height="90" fill="#0b1b33"/>',
        _text(55, 42, "U.S. VIOLENT CRIME & ECONOMIC CONDITIONS", "title"),
        _text(
            55,
            67,
            "2023 cross-sectional analysis · FBI reported offenses + Census ACS 1-year estimates · association, not causation",
            "subtitle",
        ),
    ]

    cards = [
        ("PRIMARY SAMPLE", f"{int(diagnostics['sample_size'])} states"),
        ("REPORTING FLOOR", f"{int(diagnostics['coverage_floor_pct'])}% mean coverage"),
        ("MODEL FIT", f"R² {diagnostics['r_squared']:.3f}"),
        ("UNCERTAINTY", "HC3 robust SE"),
    ]
    for index, (label, value) in enumerate(cards):
        x = 55 + index * 322.5
        parts.extend(
            [
                f'<rect x="{x:.1f}" y="112" width="292.5" height="98" rx="12" fill="#ffffff" stroke="#dde5ef"/>',
                _text(x + 20, 143, label, "kpi-label"),
                _text(x + 20, 180, value, "kpi"),
            ]
        )

    # Descriptive scatterplot.
    panel_x, panel_y, panel_w, panel_h = 55, 235, 640, 345
    plot_x, plot_y, plot_w, plot_h = 105, 302, 540, 220
    parts.extend(
        [
            f'<rect x="{panel_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" rx="12" fill="#ffffff" stroke="#dde5ef"/>',
            _text(
                panel_x + 22,
                panel_y + 34,
                "Unemployment and reported violent crime",
                "panel-title",
            ),
            _text(
                panel_x + 22,
                panel_y + 54,
                "Each point is one state in the primary sample; line is an unadjusted trend",
                "panel-sub",
            ),
        ]
    )
    x_low, x_high = 2.4, 5.7
    y_low, y_high = 75.0, 775.0
    for tick in [100, 200, 300, 400, 500, 600, 700]:
        y = _scale(tick, y_low, y_high, plot_y + plot_h, plot_y)
        parts.append(
            f'<line x1="{plot_x}" y1="{y:.1f}" x2="{plot_x + plot_w}" y2="{y:.1f}" stroke="#e8edf4"/>'
        )
        parts.append(_text(plot_x - 9, y + 3, str(tick), "axis", "end"))
    for tick in [2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5]:
        x = _scale(tick, x_low, x_high, plot_x, plot_x + plot_w)
        parts.append(
            f'<line x1="{x:.1f}" y1="{plot_y}" x2="{x:.1f}" y2="{plot_y + plot_h}" stroke="#eef2f7"/>'
        )
        parts.append(_text(x, plot_y + plot_h + 18, f"{tick:.1f}", "axis", "middle"))

    slope, intercept = np.polyfit(
        sample["unemployment_rate_pct"], sample["violent_crime_rate_per_100k"], 1
    )
    line_y1 = slope * x_low + intercept
    line_y2 = slope * x_high + intercept
    parts.append(
        f'<line x1="{plot_x}" y1="{_scale(line_y1, y_low, y_high, plot_y + plot_h, plot_y):.1f}" '
        f'x2="{plot_x + plot_w}" y2="{_scale(line_y2, y_low, y_high, plot_y + plot_h, plot_y):.1f}" '
        'stroke="#ef8354" stroke-width="2.5"/>'
    )
    for row in sample.itertuples():
        x = _scale(row.unemployment_rate_pct, x_low, x_high, plot_x, plot_x + plot_w)
        y = _scale(
            row.violent_crime_rate_per_100k, y_low, y_high, plot_y + plot_h, plot_y
        )
        title = (
            f"{row.state}: {row.violent_crime_rate_per_100k:.1f} per 100k; "
            f"unemployment {row.unemployment_rate_pct:.2f}%"
        )
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#2878b5" fill-opacity="0.78" stroke="#ffffff" stroke-width="1"><title>{escape(title)}</title></circle>'
        )
    correlation = correlations.loc[
        "violent_crime_rate_per_100k", "unemployment_rate_pct"
    ]
    parts.extend(
        [
            _text(
                plot_x + plot_w / 2,
                panel_y + panel_h - 20,
                "ACS unemployment rate (%)",
                "small",
                "middle",
            ),
            _text(
                panel_x + 22,
                panel_y + panel_h - 20,
                f"Pearson r = {correlation:.2f}",
                "label",
            ),
        ]
    )

    # Adjusted coefficient plot.
    panel_x, panel_y, panel_w, panel_h = 720, 235, 625, 345
    coef_x, coef_w = 810, 485
    coef_low, coef_high = -80.0, 140.0
    parts.extend(
        [
            f'<rect x="{panel_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" rx="12" fill="#ffffff" stroke="#dde5ef"/>',
            _text(panel_x + 22, panel_y + 34, "Adjusted OLS estimates", "panel-title"),
            _text(
                panel_x + 22,
                panel_y + 54,
                "Point estimate and 95% CI using HC3 robust standard errors",
                "panel-sub",
            ),
        ]
    )
    for tick in [-75, -50, -25, 0, 25, 50, 75, 100, 125]:
        x = _scale(tick, coef_low, coef_high, coef_x, coef_x + coef_w)
        stroke = "#94a3b8" if tick == 0 else "#eef2f7"
        stroke_width = "1.6" if tick == 0 else "1"
        parts.append(
            f'<line x1="{x:.1f}" y1="315" x2="{x:.1f}" y2="495" stroke="{stroke}" stroke-width="{stroke_width}"/>'
        )
        parts.append(_text(x, 520, str(tick), "axis", "middle"))
    coefficient_rows = [
        (
            "unemployment_rate_pct",
            "Unemployment",
            "+1 percentage point",
            355,
            "#ef8354",
        ),
        ("median_income_10k", "Median income", "+$10,000", 445, "#2878b5"),
    ]
    for term, label, unit, y, color in coefficient_rows:
        row = coefficients.loc[term]
        low_x = _scale(row["ci_95_lower"], coef_low, coef_high, coef_x, coef_x + coef_w)
        high_x = _scale(
            row["ci_95_upper"], coef_low, coef_high, coef_x, coef_x + coef_w
        )
        estimate_x = _scale(
            row["estimate"], coef_low, coef_high, coef_x, coef_x + coef_w
        )
        parts.extend(
            [
                _text(panel_x + 22, y - 5, label, "label"),
                _text(panel_x + 22, y + 13, unit, "axis"),
                f'<line x1="{low_x:.1f}" y1="{y}" x2="{high_x:.1f}" y2="{y}" stroke="{color}" stroke-width="4" stroke-linecap="round"/>',
                f'<circle cx="{estimate_x:.1f}" cy="{y}" r="7" fill="{color}" stroke="#ffffff" stroke-width="2"/>',
                _text(
                    coef_x + coef_w,
                    y - 13,
                    f"{row['estimate']:+.1f}  (p={row['p_value']:.3f})",
                    "value",
                    "end",
                ),
            ]
        )
    parts.append(
        _text(
            coef_x + coef_w / 2,
            551,
            "Change in reported violent offenses per 100,000",
            "small",
            "middle",
        )
    )

    # Ranked states.
    panel_x, panel_y, panel_w, panel_h = 55, 605, 745, 235
    parts.extend(
        [
            f'<rect x="{panel_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" rx="12" fill="#ffffff" stroke="#dde5ef"/>',
            _text(
                panel_x + 22,
                panel_y + 34,
                "Highest reported violent-crime rates in the sample",
                "panel-title",
            ),
            _text(
                panel_x + 22,
                panel_y + 54,
                "Reported offenses per 100,000 residents; not adjusted for demographics",
                "panel-sub",
            ),
        ]
    )
    ranked = sample.nlargest(6, "violent_crime_rate_per_100k")
    bar_start, bar_max_width = panel_x + 155, 500
    max_value = ranked["violent_crime_rate_per_100k"].max()
    for index, row in enumerate(ranked.itertuples()):
        y = panel_y + 78 + index * 24
        bar_width = row.violent_crime_rate_per_100k / max_value * bar_max_width
        parts.extend(
            [
                _text(bar_start - 10, y + 9, row.state, "label", "end"),
                f'<rect x="{bar_start}" y="{y}" width="{bar_width:.1f}" height="13" rx="4" fill="#2878b5"/>',
                _text(
                    bar_start + bar_width + 8,
                    y + 11,
                    f"{row.violent_crime_rate_per_100k:.1f}",
                    "value",
                ),
            ]
        )

    # Interpretation card.
    panel_x, panel_y, panel_w, panel_h = 825, 605, 520, 235
    unemployment = coefficients.loc["unemployment_rate_pct"]
    income = coefficients.loc["median_income_10k"]
    parts.extend(
        [
            f'<rect x="{panel_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" rx="12" fill="#ffffff" stroke="#dde5ef"/>',
            _text(panel_x + 22, panel_y + 34, "What the model supports", "panel-title"),
            _text(
                panel_x + 22,
                panel_y + 67,
                f"• Unemployment: {unemployment['estimate']:+.1f} per 100k (p={unemployment['p_value']:.3f})",
                "takeaway",
            ),
            _text(
                panel_x + 22,
                panel_y + 95,
                f"• Income: {income['estimate']:+.1f} per 100k (p={income['p_value']:.3f})",
                "takeaway",
            ),
            _text(
                panel_x + 22,
                panel_y + 130,
                "Income is directionally negative but not conclusive at α=.05",
                "small",
            ),
            _text(
                panel_x + 22,
                panel_y + 154,
                "The model explains a modest share of cross-state variation",
                "small",
            ),
            _text(
                panel_x + 22,
                panel_y + 178,
                "No causal claim: reporting, omitted variables, and ecology matter",
                "small",
            ),
            _text(
                panel_x + 22,
                panel_y + 207,
                "Primary model excludes seven states below the 90% coverage floor",
                "note",
            ),
        ]
    )

    parts.extend(
        [
            _text(
                55,
                875,
                "Sources: FBI Crime Data Explorer monthly UCR submissions; U.S. Census Bureau 2023 ACS 1-year tables B19013 and B23025.",
                "note",
            ),
            "</svg>",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return output_path
