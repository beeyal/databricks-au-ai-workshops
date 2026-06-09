"""
AEMO AI Governance Hub — Main Streamlit Application
====================================================
Entry point.  All SQL lives in queries.py (imported as q).
Chart builders live in charts.py (imported as c).
Shared constants/config in config.py.

Run locally:
    streamlit run app.py

Run via Databricks Apps:
    See app.yaml
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import queries as q
import charts as c
from config import (
    APP_TITLE,
    APP_SUBTITLE,
    APP_ICON,
    COLOUR_TEAL,
    COLOUR_ACCENT,
    COLOUR_NAVY,
    COLOUR_ERROR,
    CHART_PALETTE,
    TIME_WINDOWS,
    DEFAULT_TIME_WINDOW_INDEX,
)

# ---------------------------------------------------------------------------
# Page config — must be the very first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Load external CSS (graceful fallback if style.css absent)
# ---------------------------------------------------------------------------
_css_path = Path(__file__).parent / "style.css"
if _css_path.exists():
    st.markdown(f"<style>{_css_path.read_text()}</style>", unsafe_allow_html=True)
else:
    # Minimal fallback — mirrors the design tokens in style.css
    st.markdown(
        """
        <style>
        body, .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"] {
            background-color: #0D1421 !important;
            color: #E6EDF3 !important;
            font-family: 'DM Sans', Inter, sans-serif !important;
        }
        .stApp > div { background-color: #0D1421 !important; }
        footer, #MainMenu, header[data-testid="stHeader"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Sticky branded header
# ---------------------------------------------------------------------------
now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%M UTC")
st.markdown(
    f"""
    <div class="aemo-header">
        <div>
            <div class="aemo-title">⚡ {APP_TITLE}</div>
            <div class="aemo-subtitle">{APP_SUBTITLE}</div>
        </div>
        <div class="aemo-timestamp">Live as of<br><b>{now_str}</b></div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Period selector — top-right narrow column
# ---------------------------------------------------------------------------
_window_labels = [tw["label"] for tw in TIME_WINDOWS]
_pad, _sel_col = st.columns([5, 1])
with _sel_col:
    period_label = st.selectbox(
        "Period",
        _window_labels,
        index=DEFAULT_TIME_WINDOW_INDEX,
        label_visibility="collapsed",
        key="global_period",
    )

period_days: int = next(tw["days"] for tw in TIME_WINDOWS if tw["label"] == period_label)

# ---------------------------------------------------------------------------
# Helper: human-readable token / number formatting
# ---------------------------------------------------------------------------
def _fmt(n: int | float) -> str:
    n = int(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return f"{n:,}"


def _section(title: str) -> None:
    """Render a styled section header using the design-system class."""
    st.markdown(
        f'<div class="gs-section-header"><span class="gs-section-title">{title}</span></div>',
        unsafe_allow_html=True,
    )


# ===========================================================================
# Tab routing
# ===========================================================================
tab_overview, tab_usage, tab_genie, tab_gov, tab_budget = st.tabs(
    [
        "📊 Overview",
        "🤖 AI Usage",
        "💬 Genie Spaces",
        "🛡️ Governance",
        "💰 Budget & Policies",
    ]
)


# ===========================================================================
# TAB 1 — OVERVIEW
# ===========================================================================
with tab_overview:

    # ── KPI strip ──────────────────────────────────────────────────────────
    with st.spinner("Loading KPIs…"):
        kpis = q.get_overview_kpis(period_days)

    total_requests = kpis.get("total_requests", 0)
    total_tokens   = kpis.get("total_tokens", 0)
    unique_users   = kpis.get("unique_users", 0)
    top_model      = kpis.get("top_model", "N/A")
    est_cost_usd   = kpis.get("est_cost_usd", 0.0)

    # Shorten model label if too long for the card
    top_model_short = top_model if len(top_model) <= 22 else top_model[:19] + "…"

    st.markdown(
        f"""
        <div class="gs-kpi-grid" style="grid-template-columns:repeat(5,1fr);">
            <div class="gs-card gs-card--accent">
                <div class="gs-kpi-label">Total Requests</div>
                <div class="gs-kpi-value">{_fmt(total_requests)}</div>
                <div class="gs-kpi-hint">{period_label}</div>
            </div>
            <div class="gs-card gs-card--accent">
                <div class="gs-kpi-label">Total Tokens</div>
                <div class="gs-kpi-value">{_fmt(total_tokens)}</div>
                <div class="gs-kpi-hint">Input + Output</div>
            </div>
            <div class="gs-card gs-card--accent">
                <div class="gs-kpi-label">Unique Users</div>
                <div class="gs-kpi-value">{_fmt(unique_users)}</div>
                <div class="gs-kpi-hint">Principals</div>
            </div>
            <div class="gs-card gs-card--accent">
                <div class="gs-kpi-label">Top Model</div>
                <div class="gs-kpi-value" style="font-size:1rem;word-break:break-all;">{top_model_short}</div>
                <div class="gs-kpi-hint">By requests</div>
            </div>
            <div class="gs-card gs-card--accent">
                <div class="gs-kpi-label">Est. Cost</div>
                <div class="gs-kpi-value">${est_cost_usd:,.2f}</div>
                <div class="gs-kpi-hint">USD (blended)</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Daily request trend ────────────────────────────────────────────────
    _section("Daily Request Trend")
    with st.spinner("Loading trend…"):
        trend_df = q.get_daily_trend(period_days)

    if not trend_df.empty:
        plot_df = trend_df.rename(columns={
            "date": "date",
            "request_count": "requests",
            "total_tokens": "tokens",
            "unique_users": "active_users",
        })
        for col in ("requests", "tokens", "active_users"):
            if col not in plot_df.columns:
                plot_df[col] = 0
        st.plotly_chart(c.daily_trend_area(plot_df), use_container_width=True)
    else:
        st.info("No daily trend data for this period.")

    # ── Two-column section ─────────────────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        _section("Model Breakdown")
        with st.spinner("Loading model breakdown…"):
            model_df = q.get_model_breakdown(period_days)
        if not model_df.empty:
            plot_m = model_df.rename(columns={
                "destination_model": "model",
                "request_count": "requests",
                "total_tokens": "tokens",
            })
            for col in ("requests", "tokens"):
                if col not in plot_m.columns:
                    plot_m[col] = 0
            st.plotly_chart(c.model_breakdown_bar(plot_m), use_container_width=True)
        else:
            st.info("No model data available.")

    with col_right:
        _section("Top Users")
        with st.spinner("Loading top users…"):
            users_df = q.get_top_users(period_days)
        if not users_df.empty:
            plot_u = users_df.rename(columns={
                "requester": "user",
                "request_count": "requests",
                "requester_type": "requester_type",
            })
            _rtype_map = {
                "USER": "human",
                "SERVICE_PRINCIPAL": "service",
                "JOB": "automated",
                "NOTEBOOK": "automated",
                "PIPELINE": "automated",
                "MODEL_SERVING": "api",
                "GENIE": "api",
                "AGENT": "api",
            }
            plot_u["requester_type"] = (
                plot_u["requester_type"]
                .str.upper()
                .map(_rtype_map)
                .fillna("other")
            )
            st.plotly_chart(c.top_users_bar(plot_u), use_container_width=True)
        else:
            st.info("No user data available.")


# ===========================================================================
# TAB 2 — AI USAGE
# ===========================================================================
with tab_usage:

    # ── Row 1: status donut + latency gauges ───────────────────────────────
    col_s, col_l = st.columns(2)

    with col_s:
        _section("Status Code Distribution")
        with st.spinner("Loading status codes…"):
            status_df = q.get_status_breakdown(period_days)
        if not status_df.empty:
            plot_st = status_df.rename(columns={
                "status_code": "status",
                "count": "count",
            })
            st.plotly_chart(c.status_donut(plot_st), use_container_width=True)
        else:
            st.info("No status code data for this period.")

    with col_l:
        _section("API Latency Percentiles")
        with st.spinner("Loading latency…"):
            latency = q.get_latency_percentiles(period_days)
        st.plotly_chart(
            c.latency_gauge(
                p50=latency.get("p50", 0.0),
                p90=latency.get("p90", 0.0),
                p99=latency.get("p99", 0.0),
            ),
            use_container_width=True,
        )

    # ── Hourly heatmap (full width) ────────────────────────────────────────
    _section("Hourly Usage Heatmap")
    with st.spinner("Loading heatmap…"):
        heatmap_df = q.get_hourly_heatmap(period_days)
    if not heatmap_df.empty:
        plot_h = heatmap_df.rename(columns={
            "hour_of_day": "hour",
            "day_of_week": "day_of_week",
            "request_count": "requests",
        })
        st.plotly_chart(c.hourly_heatmap(plot_h), use_container_width=True)
    else:
        st.info("No heatmap data for this period.")

    # ── Guardrail events ───────────────────────────────────────────────────
    _section("Guardrail Events")
    with st.spinner("Loading guardrail events…"):
        guardrail_df = q.get_guardrail_events(period_days)
    if not guardrail_df.empty:
        plot_g = guardrail_df.rename(columns={
            "blocked_count": "blocked",
            "pii_triggers": "pii",
            "safety_triggers": "safety",
        })
        st.plotly_chart(c.guardrail_events_line(plot_g), use_container_width=True)
    else:
        st.info("No guardrail events in this period.")

    # ── Rate limit events table ────────────────────────────────────────────
    _section("Rate Limit Events (HTTP 429)")
    with st.spinner("Loading rate limit events…"):
        rate_df = q.get_rate_limit_events(period_days)
    if not rate_df.empty:
        st.dataframe(rate_df, use_container_width=True, hide_index=True)
    else:
        st.info("No rate-limit events in this period.")

    # ── Model performance table ────────────────────────────────────────────
    _section("Model Performance Summary")
    with st.spinner("Loading model performance…"):
        model_perf_df = q.get_model_breakdown(period_days)
    if not model_perf_df.empty:
        display_cols = {
            "destination_model": "Model",
            "request_count": "Requests",
            "total_tokens": "Total Tokens",
            "avg_latency": "Avg Latency (ms)",
            "error_rate": "Error Rate (%)",
        }
        show_df = model_perf_df[
            [c2 for c2 in display_cols if c2 in model_perf_df.columns]
        ].rename(columns=display_cols)
        if "Error Rate (%)" in show_df.columns:
            show_df["Error Rate (%)"] = show_df["Error Rate (%)"].apply(
                lambda x: f"{float(x):.1f}%" if x is not None else "N/A"
            )
        if "Avg Latency (ms)" in show_df.columns:
            show_df["Avg Latency (ms)"] = show_df["Avg Latency (ms)"].apply(
                lambda x: f"{float(x):,.0f}" if x is not None else "N/A"
            )
        st.dataframe(show_df, use_container_width=True, hide_index=True)
    else:
        st.info("No model performance data for this period.")


# ===========================================================================
# TAB 3 — GENIE SPACES
# ===========================================================================
with tab_genie:

    # ── Activity summary KPIs ──────────────────────────────────────────────
    _section("Total Genie Activity — All Spaces")
    with st.spinner("Loading Genie summary…"):
        genie_usage_df = q.get_genie_usage(period_days)

    if not genie_usage_df.empty:
        total_g_queries = int(genie_usage_df["queries"].sum()) if "queries" in genie_usage_df.columns else 0
        total_g_users   = int(genie_usage_df["users"].sum())   if "users"   in genie_usage_df.columns else 0
        total_g_tokens  = int(genie_usage_df["tokens"].sum())  if "tokens"  in genie_usage_df.columns else 0
    else:
        total_g_queries = 0
        total_g_users   = 0
        total_g_tokens  = 0

    st.markdown(
        f"""
        <div class="gs-kpi-grid" style="grid-template-columns:repeat(3,1fr);">
            <div class="gs-card gs-card--accent">
                <div class="gs-kpi-label">Total Queries</div>
                <div class="gs-kpi-value">{_fmt(total_g_queries)}</div>
                <div class="gs-kpi-hint">{period_label}</div>
            </div>
            <div class="gs-card gs-card--accent">
                <div class="gs-kpi-label">Unique Users</div>
                <div class="gs-kpi-value">{_fmt(total_g_users)}</div>
                <div class="gs-kpi-hint">Across all spaces</div>
            </div>
            <div class="gs-card gs-card--accent">
                <div class="gs-kpi-label">Total Tokens</div>
                <div class="gs-kpi-value">{_fmt(total_g_tokens)}</div>
                <div class="gs-kpi-hint">Input + Output</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Genie space cards ──────────────────────────────────────────────────
    _section("Genie Space Directory")
    with st.spinner("Loading Genie spaces…"):
        spaces_raw = q.get_genie_spaces()

    if spaces_raw:
        # Merge query count from usage data where space names match
        usage_lookup: dict[str, int] = {}
        if not genie_usage_df.empty and "space_name" in genie_usage_df.columns:
            usage_lookup = dict(
                zip(
                    genie_usage_df["space_name"].astype(str),
                    genie_usage_df["queries"].astype(int),
                )
            )

        cards_html = '<div class="gs-genie-grid">'
        for space in spaces_raw:
            name    = space.get("title", space.get("id", "Unnamed"))
            desc    = space.get("description") or "No description"
            creator = space.get("owner_user_name") or space.get("creator") or "Unknown"
            qcount  = usage_lookup.get(name, space.get("query_count", 0))
            desc_trunc = str(desc)[:110] + ("…" if len(str(desc)) > 110 else "")
            cards_html += f"""
            <div class="gs-genie-card">
                <div class="gs-genie-title">{name}</div>
                <div class="gs-genie-meta">{desc_trunc}</div>
                <div class="gs-genie-meta" style="margin-top:.45rem;">
                    👤 {creator} &nbsp;|&nbsp; 🔍 {int(qcount):,} queries
                </div>
            </div>"""
        cards_html += "</div>"
        st.markdown(cards_html, unsafe_allow_html=True)
    else:
        st.info("No Genie spaces found, or the workspace Genie API is not enabled.")

    # ── Genie usage bar chart ──────────────────────────────────────────────
    _section("Top Genie Spaces by Query Volume")
    if not genie_usage_df.empty:
        plot_gu = genie_usage_df.rename(columns={
            "space_name": "space_name",
            "queries": "queries",
            "users": "active_users",
        })
        st.plotly_chart(c.genie_usage_bar(plot_gu), use_container_width=True)
    else:
        st.info("No Genie usage data for this period.")


# ===========================================================================
# TAB 4 — GOVERNANCE
# ===========================================================================
with tab_gov:

    # ── Compliance status cards ────────────────────────────────────────────
    _section("Compliance Status")

    with st.spinner("Loading endpoint configs…"):
        endpoint_list = q.get_endpoint_configs()

    # Derive compliance booleans from endpoint configs
    guardrails_active     = any(ep.get("guardrails_enabled") for ep in endpoint_list)
    rate_limits_active    = any(ep.get("rate_limits_configured") for ep in endpoint_list)
    usage_tracking_active = any(ep.get("usage_tracking_enabled") for ep in endpoint_list)
    audit_active          = len(endpoint_list) > 0

    def _compliance_card(label: str, ok: bool, ok_text: str, warn_text: str) -> str:
        card_class = "gs-compliance-card gs-compliance-ok" if ok else "gs-compliance-card gs-compliance-warn"
        icon = "✅" if ok else "⚠️"
        text = ok_text if ok else warn_text
        return (
            f'<div class="{card_class}">'
            f'<div style="font-size:1.75rem;">{icon}</div>'
            f'<div style="color:#E6EDF3;font-weight:600;font-size:.88rem;margin-top:.35rem;">{text}</div>'
            f'<div class="gs-compliance-label">{label}</div>'
            f'</div>'
        )

    st.markdown(
        '<div class="gs-compliance-grid">'
        + _compliance_card("Guardrails", guardrails_active, "Guardrails Active", "No Guardrails")
        + _compliance_card("Rate Limits", rate_limits_active, "Rate Limits Set", "No Rate Limits")
        + _compliance_card("Usage Tracking", usage_tracking_active, "Tracking Enabled", "Tracking Off")
        + _compliance_card("Audit Trail", audit_active, "Endpoints Monitored", "No Endpoints Found")
        + "</div>",
        unsafe_allow_html=True,
    )

    # ── AI Gateway endpoints table ─────────────────────────────────────────
    _section("AI Gateway Endpoints")
    if endpoint_list:
        ep_df = pd.DataFrame(endpoint_list)
        _col_map = {
            "name":                   "Endpoint Name",
            "state":                  "State",
            "creator":                "Creator",
            "guardrails_enabled":     "Guardrails",
            "rate_limits_configured": "Rate Limits",
            "usage_tracking_enabled": "Usage Tracking",
        }
        show_ep = ep_df[
            [c3 for c3 in _col_map if c3 in ep_df.columns]
        ].rename(columns=_col_map)
        for bool_col in ("Guardrails", "Rate Limits", "Usage Tracking"):
            if bool_col in show_ep.columns:
                show_ep[bool_col] = show_ep[bool_col].apply(
                    lambda x: "Yes" if x else "No"
                )
        st.dataframe(show_ep, use_container_width=True, hide_index=True)
    else:
        st.info("No AI Gateway endpoints found in this workspace.")

    # ── Recent AI audit events ─────────────────────────────────────────────
    _section("Recent AI Audit Events")
    with st.spinner("Loading audit events…"):
        audit_df = q.get_access_audit_ai(period_days)
    if not audit_df.empty:
        st.dataframe(audit_df, use_container_width=True, hide_index=True)
    else:
        st.info("No AI audit events for this period.")

    # ── Model access summary by principal type ─────────────────────────────
    _section("Model Access Summary by Principal Type")
    with st.spinner("Loading access summary…"):
        access_df = q.get_top_users(period_days, limit=50)
    if not access_df.empty:
        _uc_cols = {
            "requester":      "Principal",
            "requester_type": "Type",
            "request_count":  "Requests",
            "total_tokens":   "Total Tokens",
        }
        show_uc = access_df[
            [c4 for c4 in _uc_cols if c4 in access_df.columns]
        ].rename(columns=_uc_cols)
        st.dataframe(show_uc, use_container_width=True, hide_index=True)
    else:
        st.info("No access data available for this period.")


# ===========================================================================
# TAB 5 — BUDGET & POLICIES
# ===========================================================================
with tab_budget:

    # ── Cost trend area chart ──────────────────────────────────────────────
    _section("Cost Trend by Billing Product")
    _budget_months = max(1, period_days // 30)
    with st.spinner("Loading cost trend…"):
        monthly_df = q.get_monthly_cost(months=_budget_months + 1)

    if not monthly_df.empty:
        plot_mc = monthly_df.rename(columns={"month": "date"})
        for src_col, dst_col in (
            ("model_serving_dbus", "MODEL_SERVING"),
            ("ai_gateway_dbus",    "AI_GATEWAY"),
            ("ai_functions_dbus",  "AI_FUNCTIONS"),
        ):
            if src_col in plot_mc.columns:
                plot_mc[dst_col] = plot_mc[src_col].fillna(0) * 0.07
        st.plotly_chart(c.cost_trend_area(plot_mc), use_container_width=True)
    else:
        st.info("No billing data available — system.billing.usage may require Account Admin access.")

    # ── Cost by model + budget utilisation ────────────────────────────────
    col_model_cost, col_util = st.columns(2)

    with col_model_cost:
        _section("Cost by Model")
        with st.spinner("Loading model costs…"):
            model_cost_df = q.get_cost_by_model(period_days)
        if not model_cost_df.empty:
            plot_cost = model_cost_df.rename(columns={
                "destination_model":  "model",
                "estimated_cost_usd": "cost_usd",
            })
            st.plotly_chart(c.cost_by_model_bar(plot_cost), use_container_width=True)
        else:
            st.info("No model cost data for this period.")

    with col_util:
        _section("Spend Breakdown")
        if not monthly_df.empty:
            latest = monthly_df.iloc[-1]
            ms_dbu   = float(latest.get("model_serving_dbus", 0) or 0)
            agw_dbu  = float(latest.get("ai_gateway_dbus", 0) or 0)
            aif_dbu  = float(latest.get("ai_functions_dbus", 0) or 0)
            total_dbu = ms_dbu + agw_dbu + aif_dbu or 1  # avoid /0

            for name, val in (
                ("Model Serving", ms_dbu),
                ("AI Gateway",    agw_dbu),
                ("AI Functions",  aif_dbu),
            ):
                pct = val / total_dbu * 100
                fig_g = go.Figure(
                    go.Indicator(
                        mode="gauge+number",
                        value=pct,
                        gauge={
                            "axis": {"range": [0, 100]},
                            "bar":  {"color": COLOUR_TEAL},
                            "steps": [
                                {"range": [0, 50],   "color": "#0D2A19"},
                                {"range": [50, 80],  "color": "#2A1800"},
                                {"range": [80, 100], "color": "#2A0000"},
                            ],
                            "threshold": {
                                "line": {"color": COLOUR_ERROR, "width": 3},
                                "thickness": 0.75,
                                "value": 80,
                            },
                        },
                        title={"text": name, "font": {"size": 12}},
                        number={"suffix": "%"},
                    )
                )
                fig_g.update_layout(
                    template="plotly_dark",
                    height=200,
                    margin=dict(l=16, r=16, t=36, b=8),
                )
                st.plotly_chart(fig_g, use_container_width=True)
        else:
            st.info("Billing data not available for utilisation gauges.")

    # ── Rate limit policy summary ──────────────────────────────────────────
    _section("Rate Limit Policy Summary")
    with st.spinner("Loading rate policies…"):
        ep_configs = q.get_endpoint_configs()

    if ep_configs:
        rate_rows = []
        for ep in ep_configs:
            rate_rows.append({
                "Endpoint":       ep.get("name", "Unknown"),
                "State":          ep.get("state", "UNKNOWN"),
                "Rate Limits":    "Configured" if ep.get("rate_limits_configured") else "None",
                "Guardrails":     "Active" if ep.get("guardrails_enabled") else "None",
                "Usage Tracking": "Enabled" if ep.get("usage_tracking_enabled") else "Disabled",
                "Creator":        ep.get("creator", "Unknown"),
            })
        st.dataframe(pd.DataFrame(rate_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No endpoint data — ensure your workspace has AI Gateway endpoints configured.")
