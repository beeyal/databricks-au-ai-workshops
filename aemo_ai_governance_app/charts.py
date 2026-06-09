"""
GridSense Intelligence Hub — Chart Builders
AEMO AI Governance · Plotly figure factories

Color palette
  AEMO navy   #003A5C
  AEMO teal   #00A651
  AEMO orange #F5A623
  AEMO red    #E74C3C
  AEMO grey   #6B7A8D
  Gridsense accent (teal) #00A693

All figures use the shared LAYOUT base dict and return go.Figure objects.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

AEMO_NAVY   = "#003A5C"
AEMO_TEAL   = "#00A651"
AEMO_ORANGE = "#F5A623"
AEMO_RED    = "#E74C3C"
AEMO_GREY   = "#6B7A8D"

GS_ACCENT   = "#00A693"   # GridSense teal
GS_SUCCESS  = "#1B8A4A"
GS_WARNING  = "#F59E0B"
GS_DANGER   = "#C0392B"
GS_NEUTRAL  = "#8B949E"

# Status-code colour mapping
STATUS_COLORS = {
    "200": GS_SUCCESS,
    "400": GS_WARNING,
    "429": AEMO_ORANGE,
    "5xx": GS_DANGER,
}

# Model palette (cycle if more models than entries)
MODEL_PALETTE = [
    GS_ACCENT, AEMO_NAVY, AEMO_ORANGE, AEMO_TEAL,
    "#7C3AED", "#0EA5E9", "#EC4899", AEMO_GREY,
]

# Requester-type palette
REQUESTER_COLORS = {
    "human":      GS_ACCENT,
    "service":    AEMO_NAVY,
    "automated":  AEMO_ORANGE,
    "api":        AEMO_TEAL,
    "other":      AEMO_GREY,
}

FONT_FAMILY = "DM Sans, Inter, system-ui, sans-serif"

LAYOUT = dict(
    font=dict(family=FONT_FAMILY, color="#E6EDF3", size=12),
    paper_bgcolor="#161B22",
    plot_bgcolor="#0D1117",
    margin=dict(l=16, r=16, t=36, b=16),
    legend=dict(
        bgcolor="rgba(22,27,34,0.85)",
        bordercolor="#30363D",
        borderwidth=1,
        font=dict(size=11),
    ),
    colorway=MODEL_PALETTE,
    xaxis=dict(
        gridcolor="#30363D",
        linecolor="#30363D",
        tickcolor="#30363D",
        zerolinecolor="#30363D",
    ),
    yaxis=dict(
        gridcolor="#30363D",
        linecolor="#30363D",
        tickcolor="#30363D",
        zerolinecolor="#30363D",
    ),
)


def _apply_layout(fig: go.Figure, **overrides) -> go.Figure:
    """Merge LAYOUT base dict with caller overrides, then apply."""
    base = dict(LAYOUT)
    # Deep-merge axis overrides if present
    for key in ("xaxis", "yaxis", "xaxis2", "yaxis2"):
        if key in overrides and key in base:
            merged = dict(base[key])
            merged.update(overrides.pop(key))
            overrides[key] = merged
    base.update(overrides)
    fig.update_layout(**base)
    return fig


# ---------------------------------------------------------------------------
# 1. daily_trend_area — requests + tokens + users (dual axis)
# ---------------------------------------------------------------------------

def daily_trend_area(df: pd.DataFrame) -> go.Figure:
    """
    Stacked area chart of daily request volume and token usage on a dual axis.

    Expected columns:
        date          (date/datetime)
        requests      (int)
        tokens        (int)
        active_users  (int)
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Area: tokens (secondary, lighter)
    fig.add_trace(
        go.Scatter(
            x=df["date"], y=df["tokens"],
            name="Tokens",
            fill="tozeroy",
            mode="lines",
            line=dict(color=AEMO_NAVY, width=1.5),
            fillcolor="rgba(0,58,92,0.25)",
            hovertemplate="%{y:,.0f} tokens<extra></extra>",
        ),
        secondary_y=True,
    )

    # Area: requests (primary)
    fig.add_trace(
        go.Scatter(
            x=df["date"], y=df["requests"],
            name="Requests",
            fill="tozeroy",
            mode="lines",
            line=dict(color=GS_ACCENT, width=2),
            fillcolor="rgba(0,166,147,0.20)",
            hovertemplate="%{y:,.0f} requests<extra></extra>",
        ),
        secondary_y=False,
    )

    # Line: active users (primary, no fill)
    fig.add_trace(
        go.Scatter(
            x=df["date"], y=df["active_users"],
            name="Active Users",
            mode="lines+markers",
            line=dict(color=AEMO_ORANGE, width=2, dash="dot"),
            marker=dict(size=4),
            hovertemplate="%{y:,d} users<extra></extra>",
        ),
        secondary_y=False,
    )

    _apply_layout(
        fig,
        title=dict(text="Daily API Usage Trend", font=dict(size=13), x=0.02, xanchor="left"),
        yaxis=dict(title=dict(text="Requests / Users", font=dict(size=11)), gridcolor="#30363D", linecolor="#30363D", tickcolor="#30363D", zerolinecolor="#30363D"),
        yaxis2=dict(title=dict(text="Tokens", font=dict(size=11)), gridcolor="#30363D", linecolor="#30363D", tickcolor="#30363D", zerolinecolor="#30363D"),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(22,27,34,0.85)", bordercolor="#30363D", borderwidth=1, font=dict(size=11)),
    )
    return fig


# ---------------------------------------------------------------------------
# 2. model_breakdown_bar — horizontal bar by request count, colored by tokens
# ---------------------------------------------------------------------------

def model_breakdown_bar(df: pd.DataFrame) -> go.Figure:
    """
    Horizontal bar chart of models by request count.
    Bar color encodes token volume (continuous scale).

    Expected columns:
        model         (str)
        requests      (int)
        tokens        (int)
    """
    df_sorted = df.sort_values("requests", ascending=True)

    fig = go.Figure(go.Bar(
        x=df_sorted["requests"],
        y=df_sorted["model"],
        orientation="h",
        marker=dict(
            color=df_sorted["tokens"],
            colorscale=[[0, AEMO_NAVY], [0.5, GS_ACCENT], [1, AEMO_ORANGE]],
            colorbar=dict(
                title=dict(text="Tokens", font=dict(size=11)),
                thickness=10,
                len=0.6,
                bgcolor="rgba(22,27,34,0)",
                bordercolor="#30363D",
                tickcolor="#8B949E",
                tickfont=dict(size=10),
            ),
            line=dict(color="rgba(0,0,0,0)", width=0),
        ),
        hovertemplate="<b>%{y}</b><br>Requests: %{x:,.0f}<extra></extra>",
    ))

    _apply_layout(
        fig,
        title=dict(text="Requests by Model", font=dict(size=13), x=0.02, xanchor="left"),
        xaxis=dict(title=dict(text="Request Count", font=dict(size=11)), gridcolor="#30363D", linecolor="#30363D", tickcolor="#30363D", zerolinecolor="#30363D"),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor="#30363D", tickcolor="#30363D", zerolinecolor="#30363D"),
        bargap=0.25,
    )
    return fig


# ---------------------------------------------------------------------------
# 3. top_users_bar — horizontal bar with requester_type color coding
# ---------------------------------------------------------------------------

def top_users_bar(df: pd.DataFrame) -> go.Figure:
    """
    Horizontal bar of top users / service principals by request count.
    Bars are colored by requester_type.

    Expected columns:
        user            (str)  — display name / principal
        requests        (int)
        requester_type  (str)  — human | service | automated | api | other
    """
    df_sorted = df.sort_values("requests", ascending=True).tail(20)

    # Build one trace per requester_type so the legend is clean
    fig = go.Figure()
    for rtype, color in REQUESTER_COLORS.items():
        subset = df_sorted[df_sorted["requester_type"] == rtype]
        if subset.empty:
            continue
        fig.add_trace(go.Bar(
            x=subset["requests"],
            y=subset["user"],
            name=rtype.title(),
            orientation="h",
            marker=dict(color=color, line=dict(color="rgba(0,0,0,0)", width=0)),
            hovertemplate="<b>%{y}</b><br>%{x:,.0f} requests<extra></extra>",
        ))

    _apply_layout(
        fig,
        title=dict(text="Top Users / Principals", font=dict(size=13), x=0.02, xanchor="left"),
        barmode="stack",
        xaxis=dict(title=dict(text="Requests", font=dict(size=11)), gridcolor="#30363D", linecolor="#30363D", tickcolor="#30363D", zerolinecolor="#30363D"),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor="#30363D", tickcolor="#30363D", zerolinecolor="#30363D"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(22,27,34,0.85)", bordercolor="#30363D", borderwidth=1, font=dict(size=11)),
        bargap=0.20,
    )
    return fig


# ---------------------------------------------------------------------------
# 4. status_donut — 200 / 400 / 429 / 5xx
# ---------------------------------------------------------------------------

def status_donut(df: pd.DataFrame) -> go.Figure:
    """
    Donut chart of HTTP status code distribution.

    Expected columns:
        status   (str)  — "200", "400", "429", "5xx"
        count    (int)
    """
    colors = [STATUS_COLORS.get(str(s), AEMO_GREY) for s in df["status"]]
    total = df["count"].sum()

    fig = go.Figure(go.Pie(
        labels=df["status"],
        values=df["count"],
        hole=0.62,
        marker=dict(
            colors=colors,
            line=dict(color="#161B22", width=2),
        ),
        textfont=dict(size=11),
        hovertemplate="<b>HTTP %{label}</b><br>%{value:,.0f} (%{percent})<extra></extra>",
        sort=False,
    ))

    fig.add_annotation(
        text=f"<b>{total:,.0f}</b><br><span style='font-size:10px;color:{GS_NEUTRAL}'>Total</span>",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=16, color="#E6EDF3"),
        align="center",
    )

    _apply_layout(
        fig,
        title=dict(text="Response Status Distribution", font=dict(size=13), x=0.02, xanchor="left"),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.08, xanchor="center", x=0.5, bgcolor="rgba(22,27,34,0.85)", bordercolor="#30363D", borderwidth=1, font=dict(size=11)),
        margin=dict(l=16, r=16, t=40, b=40),
    )
    return fig


# ---------------------------------------------------------------------------
# 5. latency_gauge — p50 / p90 / p99 side by side
# ---------------------------------------------------------------------------

def latency_gauge(p50: float, p90: float, p99: float, threshold_warn: float = 2000, threshold_danger: float = 5000) -> go.Figure:
    """
    Three Plotly indicator gauges in a single figure showing latency percentiles.

    Args:
        p50, p90, p99         : latency values in milliseconds
        threshold_warn        : yellow zone start (default 2 000 ms)
        threshold_danger      : red zone start (default 5 000 ms)
    """
    max_val = max(p99 * 1.2, threshold_danger * 1.1)

    steps = [
        dict(range=[0, threshold_warn],           color="rgba(27,138,74,0.15)"),
        dict(range=[threshold_warn, threshold_danger], color="rgba(245,158,11,0.15)"),
        dict(range=[threshold_danger, max_val],    color="rgba(192,57,43,0.15)"),
    ]

    def _gauge(value: float, title: str, col: int) -> go.Indicator:
        return go.Indicator(
            mode="gauge+number",
            value=value,
            domain=dict(x=[(col - 1) / 3, col / 3], y=[0, 1]),
            title=dict(text=title, font=dict(size=12, color=GS_NEUTRAL)),
            number=dict(suffix=" ms", font=dict(size=22, color="#E6EDF3")),
            gauge=dict(
                axis=dict(
                    range=[0, max_val],
                    tickcolor=GS_NEUTRAL,
                    tickfont=dict(size=9, color=GS_NEUTRAL),
                    dtick=threshold_warn,
                ),
                bar=dict(color=GS_ACCENT, thickness=0.6),
                bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
                steps=steps,
                threshold=dict(
                    line=dict(color=GS_DANGER, width=2),
                    thickness=0.85,
                    value=threshold_danger,
                ),
            ),
        )

    fig = go.Figure()
    fig.add_trace(_gauge(p50, "p50 Latency", 1))
    fig.add_trace(_gauge(p90, "p90 Latency", 2))
    fig.add_trace(_gauge(p99, "p99 Latency", 3))

    _apply_layout(
        fig,
        title=dict(text="API Latency Percentiles", font=dict(size=13), x=0.02, xanchor="left"),
        margin=dict(l=16, r=16, t=44, b=16),
        height=220,
    )
    return fig


# ---------------------------------------------------------------------------
# 6. hourly_heatmap — GitHub-style: hour × day_of_week colored by volume
# ---------------------------------------------------------------------------

def hourly_heatmap(df: pd.DataFrame) -> go.Figure:
    """
    Heatmap of request volume by hour-of-day (x) and day-of-week (y).

    Expected columns:
        hour         (int  0-23)
        day_of_week  (int  0=Mon … 6=Sun  OR str "Mon" … "Sun")
        requests     (int)
    """
    days_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}

    if df["day_of_week"].dtype != object:
        df = df.copy()
        df["day_of_week"] = df["day_of_week"].map(day_map)

    pivot = (
        df.pivot_table(index="day_of_week", columns="hour", values="requests", aggfunc="sum", fill_value=0)
        .reindex(days_order)
    )

    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=[f"{h:02d}:00" for h in pivot.columns],
        y=pivot.index.tolist(),
        colorscale=[
            [0.00, "#161B22"],
            [0.20, "#003A5C"],
            [0.55, "#00A651"],
            [1.00, "#F5A623"],
        ],
        hoverongaps=False,
        hovertemplate="<b>%{y} %{x}</b><br>%{z:,.0f} requests<extra></extra>",
        colorbar=dict(
            title=dict(text="Requests", font=dict(size=11)),
            thickness=10,
            len=0.75,
            bgcolor="rgba(22,27,34,0)",
            bordercolor="#30363D",
            tickcolor="#8B949E",
            tickfont=dict(size=10),
        ),
        xgap=3,
        ygap=3,
    ))

    _apply_layout(
        fig,
        title=dict(text="Request Volume Heatmap", font=dict(size=13), x=0.02, xanchor="left"),
        xaxis=dict(side="bottom", tickfont=dict(size=10), gridcolor="rgba(0,0,0,0)", linecolor="#30363D", tickcolor="#30363D", zerolinecolor="#30363D"),
        yaxis=dict(tickfont=dict(size=10), gridcolor="rgba(0,0,0,0)", linecolor="#30363D", tickcolor="#30363D", zerolinecolor="#30363D"),
        margin=dict(l=48, r=16, t=44, b=16),
    )
    return fig


# ---------------------------------------------------------------------------
# 7. cost_trend_area — stacked area: MODEL_SERVING + AI_GATEWAY + AI_FUNCTIONS
# ---------------------------------------------------------------------------

def cost_trend_area(df: pd.DataFrame) -> go.Figure:
    """
    Stacked area of daily estimated cost broken down by Databricks service tier.

    Expected columns:
        date              (date/datetime)
        MODEL_SERVING     (float USD)
        AI_GATEWAY        (float USD)
        AI_FUNCTIONS      (float USD)
    """
    layers = [
        ("AI_FUNCTIONS",  AEMO_GREY,   "rgba(107,122,141,0.30)"),
        ("AI_GATEWAY",    AEMO_NAVY,   "rgba(0,58,92,0.35)"),
        ("MODEL_SERVING", GS_ACCENT,   "rgba(0,166,147,0.35)"),
    ]

    fig = go.Figure()
    for col, line_col, fill_col in layers:
        if col not in df.columns:
            continue
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[col],
            name=col.replace("_", " ").title(),
            stackgroup="cost",
            mode="lines",
            line=dict(color=line_col, width=1.5),
            fillcolor=fill_col,
            hovertemplate=f"<b>{col}</b>: $%{{y:,.2f}}<extra></extra>",
        ))

    _apply_layout(
        fig,
        title=dict(text="Estimated Cost Trend (USD)", font=dict(size=13), x=0.02, xanchor="left"),
        yaxis=dict(title=dict(text="USD", font=dict(size=11)), tickprefix="$", gridcolor="#30363D", linecolor="#30363D", tickcolor="#30363D", zerolinecolor="#30363D"),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(22,27,34,0.85)", bordercolor="#30363D", borderwidth=1, font=dict(size=11)),
    )
    return fig


# ---------------------------------------------------------------------------
# 8. cost_by_model_bar — horizontal bar, USD cost per model
# ---------------------------------------------------------------------------

def cost_by_model_bar(df: pd.DataFrame) -> go.Figure:
    """
    Horizontal bar of estimated USD cost per model.

    Expected columns:
        model      (str)
        cost_usd   (float)
    """
    df_sorted = df.sort_values("cost_usd", ascending=True)
    n = len(df_sorted)
    colors = [MODEL_PALETTE[i % len(MODEL_PALETTE)] for i in range(n)]

    fig = go.Figure(go.Bar(
        x=df_sorted["cost_usd"],
        y=df_sorted["model"],
        orientation="h",
        marker=dict(color=colors, line=dict(color="rgba(0,0,0,0)", width=0)),
        hovertemplate="<b>%{y}</b><br>$%{x:,.4f}<extra></extra>",
    ))

    _apply_layout(
        fig,
        title=dict(text="Cost by Model (USD)", font=dict(size=13), x=0.02, xanchor="left"),
        xaxis=dict(title=dict(text="USD", font=dict(size=11)), tickprefix="$", gridcolor="#30363D", linecolor="#30363D", tickcolor="#30363D", zerolinecolor="#30363D"),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor="#30363D", tickcolor="#30363D", zerolinecolor="#30363D"),
        bargap=0.25,
    )
    return fig


# ---------------------------------------------------------------------------
# 9. guardrail_events_line — blocked + pii + safety events over time
# ---------------------------------------------------------------------------

def guardrail_events_line(df: pd.DataFrame) -> go.Figure:
    """
    Multi-line chart of guardrail event types over time.

    Expected columns:
        date     (date/datetime)
        blocked  (int)
        pii      (int)
        safety   (int)
    """
    traces = [
        ("blocked", GS_DANGER,   "solid"),
        ("pii",     AEMO_ORANGE, "dot"),
        ("safety",  GS_WARNING,  "dash"),
    ]

    fig = go.Figure()
    for col, color, dash in traces:
        if col not in df.columns:
            continue
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[col],
            name=col.title(),
            mode="lines+markers",
            line=dict(color=color, width=2, dash=dash),
            marker=dict(size=4),
            hovertemplate=f"<b>{col.title()}</b>: %{{y:,.0f}}<extra></extra>",
        ))

    _apply_layout(
        fig,
        title=dict(text="Guardrail Events Over Time", font=dict(size=13), x=0.02, xanchor="left"),
        yaxis=dict(title=dict(text="Events", font=dict(size=11)), gridcolor="#30363D", linecolor="#30363D", tickcolor="#30363D", zerolinecolor="#30363D"),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(22,27,34,0.85)", bordercolor="#30363D", borderwidth=1, font=dict(size=11)),
    )
    return fig


# ---------------------------------------------------------------------------
# 10. genie_usage_bar — horizontal bar: Genie spaces by query count
# ---------------------------------------------------------------------------

def genie_usage_bar(df: pd.DataFrame) -> go.Figure:
    """
    Horizontal bar of Genie spaces ordered by query volume.

    Expected columns:
        space_name   (str)
        queries      (int)
        active_users (int, optional — used for marker opacity)
    """
    df_sorted = df.sort_values("queries", ascending=True).tail(15)
    n = len(df_sorted)

    # Encode active_users as opacity if available
    if "active_users" in df_sorted.columns:
        max_u = df_sorted["active_users"].max() or 1
        opacities = (0.45 + 0.55 * df_sorted["active_users"] / max_u).tolist()
    else:
        opacities = [0.85] * n

    colors = [f"rgba(0,166,147,{o:.2f})" for o in opacities]

    fig = go.Figure(go.Bar(
        x=df_sorted["queries"],
        y=df_sorted["space_name"],
        orientation="h",
        marker=dict(color=colors, line=dict(color="rgba(0,0,0,0)", width=0)),
        hovertemplate="<b>%{y}</b><br>%{x:,.0f} queries<extra></extra>",
    ))

    _apply_layout(
        fig,
        title=dict(text="Genie Space Usage", font=dict(size=13), x=0.02, xanchor="left"),
        xaxis=dict(title=dict(text="Queries", font=dict(size=11)), gridcolor="#30363D", linecolor="#30363D", tickcolor="#30363D", zerolinecolor="#30363D"),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor="#30363D", tickcolor="#30363D", zerolinecolor="#30363D"),
        bargap=0.20,
    )
    return fig


# ---------------------------------------------------------------------------
# 11. model_latency_box — bar with error-bar p50/p90/p99 per model
# ---------------------------------------------------------------------------

def model_latency_box(df: pd.DataFrame) -> go.Figure:
    """
    Grouped bar chart with error bars showing p50, p90, p99 latency per model.
    Falls back to a simple bar if only p50 is present.

    Expected columns:
        model  (str)
        p50    (float, ms)
        p90    (float, ms)
        p99    (float, ms)
    """
    fig = go.Figure()

    percentiles = [
        ("p50", GS_ACCENT,   "P50 (median)"),
        ("p90", AEMO_ORANGE, "P90"),
        ("p99", GS_DANGER,   "P99"),
    ]

    for col, color, label in percentiles:
        if col not in df.columns:
            continue
        fig.add_trace(go.Bar(
            name=label,
            x=df["model"],
            y=df[col],
            marker=dict(color=color, line=dict(color="rgba(0,0,0,0)", width=0)),
            hovertemplate=f"<b>%{{x}}</b><br>{label}: %{{y:,.0f}} ms<extra></extra>",
        ))

    # Overlay an invisible scatter with p50→p99 error bars to show spread
    if all(c in df.columns for c in ("p50", "p99")):
        mid = (df["p50"] + df["p99"]) / 2
        err = (df["p99"] - df["p50"]) / 2
        fig.add_trace(go.Scatter(
            x=df["model"],
            y=mid,
            mode="markers",
            marker=dict(size=0, color="rgba(0,0,0,0)"),
            error_y=dict(
                type="data",
                array=err.tolist(),
                symmetric=True,
                color="#8B949E",
                thickness=1.5,
                width=6,
            ),
            showlegend=False,
            hoverinfo="skip",
        ))

    _apply_layout(
        fig,
        title=dict(text="Model Latency (ms) by Percentile", font=dict(size=13), x=0.02, xanchor="left"),
        barmode="group",
        bargap=0.22,
        bargroupgap=0.06,
        yaxis=dict(title=dict(text="Latency (ms)", font=dict(size=11)), gridcolor="#30363D", linecolor="#30363D", tickcolor="#30363D", zerolinecolor="#30363D"),
        xaxis=dict(tickangle=-20, gridcolor="rgba(0,0,0,0)", linecolor="#30363D", tickcolor="#30363D", zerolinecolor="#30363D"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(22,27,34,0.85)", bordercolor="#30363D", borderwidth=1, font=dict(size=11)),
    )
    return fig
