"""
USDA Agricultural Prices — cost/price squeeze dashboard.

Phase 1: a faithful replication of the two-panel "prices paid vs. prices
received" chart, crop farms and livestock farms, rebased to a common base year.

Run: python app.py
"""

import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Dash, dcc, html

import fetch_data

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_YEAR = 2019          # index rebased so this calendar year averages 100
START = f"{BASE_YEAR}-01-01"

PANELS = ["Crop farms", "Livestock farms"]

TITLE = "Agricultural Sector Price-Cost Margins"
BETA = True   # shows a "Beta" tag next to the title; set False to remove
SUBTITLE = (
    "Source: USDA NASS Agricultural Prices — prices farmers pay for inputs vs. "
    "prices they receive, monthly, {first}–{last}"
)
DISCLAIMER = "Independent project, not affiliated with or endorsed by USDA."
REPO_URL = "https://github.com/ezra-butcher/ag-prices-viz"


# ── Palette ───────────────────────────────────────────────────────────────────

INK = "#14532d"           # headline green
BODY = "#3f4a45"
COLOR_COSTS = "#c0392b"
COLOR_PRICES = "#166b4f"
FILL_SQUEEZE = "#f6b4ae"  # costs above prices
FILL_MARGIN = "#a9e0c1"   # prices above costs
GRID = "#e6e6e2"
AXIS = "#9aa3a0"

# ── Data ──────────────────────────────────────────────────────────────────────

df = fetch_data.load_cache()


def rebase(frame: pd.DataFrame, base_year: int) -> pd.DataFrame:
    """Rescale each (panel, series) so its base-year monthly mean equals 100."""
    out = []
    for (panel, series), g in frame.groupby(["panel", "series"], sort=False):
        g = g.sort_values("date")
        base = g.loc[g["year"] == base_year, "value"]
        if base.empty:
            raise ValueError(f"No {base_year} observations for {panel} / {series}")
        g = g.assign(index=g["value"] / base.mean() * 100.0)
        out.append(g)
    return pd.concat(out, ignore_index=True)


indexed = rebase(df, BASE_YEAR)
indexed = indexed[indexed["date"] >= START]

# Wide frame per panel: one column of costs, one of prices, on a shared date grid
panel_data = {}
for panel in PANELS:
    wide = (
        indexed[indexed["panel"] == panel]
        .pivot(index="date", columns="series", values="index")
        .dropna()
        .sort_index()
    )
    panel_data[panel] = wide

FIRST_DATE = min(w.index.min() for w in panel_data.values())
LAST_DATE = min(w.index.max() for w in panel_data.values())


def _with_crossings(dates, costs, prices):
    """Insert interpolated points where the two series cross.

    Without this the min/max fill traces leave small triangular slivers of the
    wrong colour at each crossover, because the shaded region only changes
    colour at grid points.
    """
    x = list(dates.astype("int64"))
    c, p = list(costs), list(prices)
    out_x, out_c, out_p = [x[0]], [c[0]], [p[0]]
    for i in range(1, len(x)):
        d0, d1 = (c[i - 1] - p[i - 1]), (c[i] - p[i])
        if d0 * d1 < 0:                      # sign flip -> exact crossing between
            t = d0 / (d0 - d1)
            xc = x[i - 1] + t * (x[i] - x[i - 1])
            yc = c[i - 1] + t * (c[i] - c[i - 1])
            out_x.append(xc)
            out_c.append(yc)
            out_p.append(yc)
        out_x.append(x[i])
        out_c.append(c[i])
        out_p.append(p[i])
    return (
        pd.to_datetime(np.array(out_x).astype("int64")),
        np.array(out_c),
        np.array(out_p),
    )


# ── Figure ────────────────────────────────────────────────────────────────────

def build_figure() -> go.Figure:
    fig = make_subplots(
        rows=1,
        cols=2,
        shared_yaxes=True,
        horizontal_spacing=0.16,
        subplot_titles=[p.upper() for p in PANELS],
    )

    for col, panel in enumerate(panel_data, start=1):
        wide = panel_data[panel]
        dates, costs, prices = wide.index, wide["Costs"].to_numpy(), wide["Prices"].to_numpy()
        fx, fc, fp = _with_crossings(dates, costs, prices)

        # Conditional band: two fill pairs, each anchored to the costs line.
        # min(costs, prices) shades only where costs sit above prices, and
        # max(costs, prices) only where prices sit above costs.
        for bound, fill in (
            (np.minimum(fc, fp), FILL_SQUEEZE),
            (np.maximum(fc, fp), FILL_MARGIN),
        ):
            fig.add_trace(
                go.Scatter(
                    x=fx, y=fc, mode="lines", line=dict(width=0),
                    hoverinfo="skip", showlegend=False,
                ),
                row=1, col=col,
            )
            fig.add_trace(
                go.Scatter(
                    x=fx, y=bound, mode="lines", line=dict(width=0),
                    fill="tonexty", fillcolor=fill,
                    hoverinfo="skip", showlegend=False,
                ),
                row=1, col=col,
            )

        for name, values, color in (
            ("Costs", costs, COLOR_COSTS),
            ("Prices", prices, COLOR_PRICES),
        ):
            fig.add_trace(
                go.Scatter(
                    x=dates, y=values, mode="lines", name=name,
                    line=dict(color=color, width=1.8),
                    showlegend=False,
                    hovertemplate=f"{name}: %{{y:.1f}}<extra></extra>",
                ),
                row=1, col=col,
            )
            # End-point dot and label, mirroring the source chart
            fig.add_trace(
                go.Scatter(
                    x=[dates[-1]], y=[values[-1]], mode="markers",
                    marker=dict(color=color, size=6),
                    hoverinfo="skip", showlegend=False,
                ),
                row=1, col=col,
            )
            fig.add_annotation(
                x=dates[-1], y=values[-1],
                text=f"<b>{name} {values[-1]:.0f}</b>",
                xanchor="left", xshift=9, yanchor="middle",
                showarrow=False, font=dict(size=11, color=color),
                row=1, col=col,
            )

        fig.add_hline(
            y=100, line=dict(color=AXIS, width=1, dash="dash"),
            row=1, col=col,
        )


    # Subplot titles are the only annotations added before ours — left-align
    # them over their panels instead of centring.
    for ann, x in zip(fig.layout.annotations[: len(PANELS)], (0.0, 0.58)):
        ann.update(
            x=x, xanchor="left", xref="paper",
            font=dict(size=12.5, color=INK, family="Helvetica Neue, Arial, sans-serif"),
        )

    lo = min(w.min().min() for w in panel_data.values())
    hi = max(w.max().max() for w in panel_data.values())

    fig.update_xaxes(
        range=[FIRST_DATE - pd.DateOffset(months=3), LAST_DATE + pd.DateOffset(months=3)],
        dtick="M24", tickformat="%Y",
        showgrid=True, gridcolor=GRID,
        showline=True, linecolor=AXIS, ticks="outside", tickcolor=AXIS,
        tickfont=dict(size=10, color=BODY),
    )
    fig.update_yaxes(
        range=[lo - 5, hi + 8], dtick=20, tick0=100,
        showgrid=True, gridcolor=GRID,
        showline=False, zeroline=False,
        tickfont=dict(size=10, color=BODY),
    )
    fig.update_yaxes(
        title_text=f"Index ({BASE_YEAR} avg = 100)",
        title_font=dict(size=10.5, color=BODY),
        row=1, col=1,
    )

    fig.update_layout(
        height=430,
        margin=dict(l=60, r=95, t=34, b=30),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Helvetica Neue, Arial, sans-serif", color=BODY),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="white", font_size=11),
    )
    return fig


# ── App ───────────────────────────────────────────────────────────────────────

# Set DASH_URL_BASE_PATHNAME (e.g. "/ag-prices/", both slashes required) when
# serving behind a path-mounted proxy such as a shared Tailscale Funnel port.
app = Dash(
    __name__,
    title="USDA Price-Cost Margins",
    url_base_pathname=os.environ.get("DASH_URL_BASE_PATHNAME", "/"),
)
server = app.server


def legend_key(color: str, label: str):
    return html.Span(
        [html.Span(className="swatch", style={"backgroundColor": color}), label],
        className="legend-key",
    )


app.layout = html.Div(
    className="page",
    children=[
        html.H1(
            [TITLE] + ([html.Span("Beta", className="beta-tag")] if BETA else []),
            className="title",
        ),
        html.P(
            f"{SUBTITLE.format(first=f'{FIRST_DATE:%B %Y}', last=f'{LAST_DATE:%B %Y}')}. {DISCLAIMER}",
            className="subtitle",
        ),
        dcc.Graph(
            id="squeeze",
            figure=build_figure(),
            config={"displaylogo": False, "responsive": True,
                    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"]},
        ),
        html.Div(
            className="legend",
            children=[
                legend_key(FILL_SQUEEZE, "Costs exceed prices"),
                legend_key(FILL_MARGIN, "Prices exceed costs"),
            ],
        ),
        html.Div(
            className="footer",
            children=[
                html.A("View on GitHub", href=REPO_URL, target="_blank", className="repo-link"),
            ],
        ),
    ],
)


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8053)
