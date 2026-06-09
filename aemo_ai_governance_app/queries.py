"""
queries.py — AEMO AI Governance App
All data-fetching functions backed by Databricks SDK statement execution.
Warehouse: 9d8a677b3c55b8a7

Auth strategy:
  - Databricks Apps runtime: WorkspaceClient() with no args — SDK picks up
    DATABRICKS_HOST + DATABRICKS_TOKEN injected by the Apps platform via OAuth
    on behalf of the logged-in user (or the App's service principal).
  - Local dev with a named profile: set DATABRICKS_CONFIG_PROFILE=e2-demo-west
    in the environment, or pass profile= explicitly. We detect the Apps context
    via the DATABRICKS_RUNTIME_ENV variable that the platform sets.
"""

from __future__ import annotations

import os
import time
from typing import Any

import pandas as pd
import streamlit as st
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState


# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

def get_client() -> WorkspaceClient:
    """Return a WorkspaceClient.

    Priority order:
    1. OBO user-forwarded token (X-Forwarded-Access-Token header)
    2. SDK OAuth using DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET (SP)
    3. Local profile fallback for development
    """
    host = os.environ.get("DATABRICKS_HOST", "").rstrip("/")

    # 1. OBO — user's token forwarded by Databricks Apps
    try:
        user_token = st.context.headers.get("X-Forwarded-Access-Token", "")
        if user_token and host:
            return WorkspaceClient(host=host, token=user_token)
    except Exception:
        pass

    # 2. SDK resolves credentials from env vars automatically
    if host:
        try:
            return WorkspaceClient(host=host)
        except Exception:
            pass

    # 3. Local dev
    return WorkspaceClient(profile="dogfood")


WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "93a682dcf60dae13")

# Cost constants (approximate list-price DBU rates; adjust to contract rates)
_DBU_COST_USD = 0.07          # Model Serving / AI Gateway DBU → USD (rough)
_TOKEN_TO_DBU = 1 / 1_000_000  # 1 DBU ≈ 1 M tokens (illustrative)


# ---------------------------------------------------------------------------
# SDK statement execution helper
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def _get_cached_client(token_hash: str = "") -> WorkspaceClient:
    """Cache the WorkspaceClient. token_hash busts the cache when the token rotates."""
    host = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
    if host:
        return WorkspaceClient(host=host)
    return WorkspaceClient(profile="dogfood")


def _run_query(sql: str, timeout_secs: int = 50) -> pd.DataFrame:
    """Execute SQL via SDK statement execution and return a DataFrame.

    Uses OBO token when available (so queries run as the logged-in user),
    otherwise falls back to the SP's ambient credentials.
    """
    # Get OBO token outside cache so st.context is available
    host = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
    try:
        obo_token = st.context.headers.get("X-Forwarded-Access-Token", "")
    except Exception:
        obo_token = ""

    if obo_token and host:
        client = WorkspaceClient(host=host, token=obo_token)
    else:
        # Fall back to SP credentials (needs warehouse access granted)
        client = _get_cached_client()
    try:
        # wait_timeout must be 0 or 5-50 seconds per API contract
        wait_secs = min(max(timeout_secs, 5), 50)
        resp = client.statement_execution.execute_statement(
            warehouse_id=WAREHOUSE_ID,
            statement=sql,
            wait_timeout=f"{wait_secs}s",
        )

        # Poll if still running after initial wait
        deadline = time.monotonic() + 120
        while resp.status.state in (StatementState.PENDING, StatementState.RUNNING):
            if time.monotonic() > deadline:
                raise TimeoutError("Query exceeded 120s timeout")
            time.sleep(3)
            resp = client.statement_execution.get_statement(resp.statement_id)

        if resp.status.state != StatementState.SUCCEEDED:
            error_msg = getattr(resp.status, "error", {})
            raise RuntimeError(f"Query failed: {error_msg}")

        result = resp.result
        manifest = resp.manifest

        if not manifest or not manifest.schema or not manifest.schema.columns:
            return pd.DataFrame()

        columns = [col.name for col in manifest.schema.columns]

        if not result or not result.data_array:
            return pd.DataFrame(columns=columns)

        df = pd.DataFrame(result.data_array, columns=columns)

        # Cast numeric-looking columns
        for col in manifest.schema.columns:
            if col.type_name and col.type_name.value in (
                "INT", "LONG", "DOUBLE", "FLOAT", "DECIMAL",
            ):
                df[col.name] = pd.to_numeric(df[col.name], errors="coerce")

        return df

    except Exception as exc:
        st.warning(f"Query error: {exc}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# 1. Overview KPIs
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_overview_kpis(days: int = 30) -> dict[str, Any]:
    """Return top-level KPIs for the overview tab.

    The top_model subquery is resolved separately so that the outer query
    contains only plain aggregates (no window functions mixed with GROUP BY).
    The two CTEs are joined with CROSS JOIN to produce a single row.
    """
    sql = f"""
    WITH agg AS (
        SELECT
            COUNT(*)                                    AS total_requests,
            SUM(total_tokens)                           AS total_tokens,
            COUNT(DISTINCT requester)                   AS unique_users,
            SUM(total_tokens) * {_TOKEN_TO_DBU} * {_DBU_COST_USD} AS est_cost_usd
        FROM system.ai_gateway.usage
        WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
    ),
    top_model AS (
        SELECT
            COALESCE(destination_model, 'unknown')      AS top_model
        FROM system.ai_gateway.usage
        WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
        GROUP BY destination_model
        ORDER BY COUNT(*) DESC
        LIMIT 1
    )
    SELECT
        agg.total_requests,
        agg.total_tokens,
        agg.unique_users,
        agg.est_cost_usd,
        COALESCE(top_model.top_model, 'N/A')            AS top_model
    FROM agg
    CROSS JOIN top_model
    """
    df = _run_query(sql)
    if df.empty:
        return {
            "total_requests": 0,
            "total_tokens": 0,
            "unique_users": 0,
            "top_model": "N/A",
            "est_cost_usd": 0.0,
        }

    row = df.iloc[0]
    return {
        "total_requests": int(row.get("total_requests", 0) or 0),
        "total_tokens": int(row.get("total_tokens", 0) or 0),
        "unique_users": int(row.get("unique_users", 0) or 0),
        "top_model": str(row.get("top_model", "N/A") or "N/A"),
        "est_cost_usd": float(row.get("est_cost_usd", 0.0) or 0.0),
    }


# ---------------------------------------------------------------------------
# 2. Daily trend
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_daily_trend(days: int = 30) -> pd.DataFrame:
    sql = f"""
    SELECT
        CAST(event_time AS DATE)                    AS date,
        COUNT(*)                                    AS request_count,
        SUM(total_tokens)                           AS total_tokens,
        COUNT(DISTINCT requester)                   AS unique_users,
        SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) AS errors
    FROM system.ai_gateway.usage
    WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
    GROUP BY 1
    ORDER BY 1
    """
    df = _run_query(sql)
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


# ---------------------------------------------------------------------------
# 3. Model breakdown
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_model_breakdown(days: int = 30) -> pd.DataFrame:
    sql = f"""
    SELECT
        COALESCE(destination_model, 'unknown')      AS destination_model,
        COUNT(*)                                    AS request_count,
        SUM(total_tokens)                           AS total_tokens,
        AVG(latency_ms)                             AS avg_latency,
        SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) * 100.0
            / COUNT(*)                              AS error_rate
    FROM system.ai_gateway.usage
    WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
    GROUP BY 1
    ORDER BY request_count DESC
    """
    return _run_query(sql)


# ---------------------------------------------------------------------------
# 4. Top users
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_top_users(days: int = 30, limit: int = 20) -> pd.DataFrame:
    sql = f"""
    SELECT
        COALESCE(requester, 'unknown')              AS requester,
        COALESCE(requester_type, 'unknown')         AS requester_type,
        COUNT(*)                                    AS request_count,
        SUM(total_tokens)                           AS total_tokens
    FROM system.ai_gateway.usage
    WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
    GROUP BY 1, 2
    ORDER BY request_count DESC
    LIMIT {limit}
    """
    return _run_query(sql)


# ---------------------------------------------------------------------------
# 5. Status code breakdown
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_status_breakdown(days: int = 30) -> pd.DataFrame:
    sql = f"""
    SELECT
        CAST(status_code AS STRING)                 AS status_code,
        COUNT(*)                                    AS count,
        COUNT(*) * 100.0 / SUM(COUNT(*)) OVER ()   AS pct
    FROM system.ai_gateway.usage
    WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
    GROUP BY 1
    ORDER BY count DESC
    """
    return _run_query(sql)


# ---------------------------------------------------------------------------
# 6. Latency percentiles
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_latency_percentiles(days: int = 30) -> dict[str, float]:
    sql = f"""
    SELECT
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50,
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY latency_ms) AS p90,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99
    FROM system.ai_gateway.usage
    WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
      AND latency_ms IS NOT NULL
    """
    df = _run_query(sql)
    if df.empty:
        return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}
    row = df.iloc[0]
    return {
        "p50": float(row.get("p50", 0.0) or 0.0),
        "p90": float(row.get("p90", 0.0) or 0.0),
        "p95": float(row.get("p95", 0.0) or 0.0),
        "p99": float(row.get("p99", 0.0) or 0.0),
    }


# ---------------------------------------------------------------------------
# 7. Hourly heatmap (requests by hour-of-day × day-of-week)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_hourly_heatmap(days: int = 7) -> pd.DataFrame:
    sql = f"""
    SELECT
        HOUR(event_time)                            AS hour_of_day,
        DATE_FORMAT(event_time, 'EEEE')             AS day_of_week,
        COUNT(*)                                    AS request_count
    FROM system.ai_gateway.usage
    WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
    GROUP BY 1, 2
    ORDER BY 1, 2
    """
    return _run_query(sql)


# ---------------------------------------------------------------------------
# 8. Genie spaces (SDK — client.genie.list_spaces())
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_genie_spaces() -> list[dict]:
    """Return a list of Genie space dicts using the SDK GenieAPI.

    Uses client.genie.list_spaces() which maps to GET /api/2.0/genie/spaces
    and returns GenieSpace objects with fields:
        space_id, title, description, etag, parent_path,
        serialized_space, warehouse_id

    Returns an empty list on any error so the app degrades gracefully.
    """
    client = get_client()
    try:
        # Use REST API directly — SDK GenieAPI doesn't have list_spaces()
        import urllib.request, json as _json
        host = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
        try:
            user_token = st.context.headers.get("X-Forwarded-Access-Token", "")
        except Exception:
            user_token = ""
        token = user_token or os.environ.get("DATABRICKS_TOKEN", "")
        if not host or not token:
            cfg = client.config
            host = cfg.host.rstrip("/")
            token = cfg.token or ""
        req = urllib.request.Request(
            f"{host}/api/2.0/genie/spaces",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = _json.loads(r.read())
        spaces = data.get("spaces", [])
        return [{
            "id":            s.get("space_id", ""),
            "title":         s.get("title", "Unnamed"),
            "description":   s.get("description", ""),
            "warehouse_id":  s.get("warehouse_id", ""),
            "owner_user_name": s.get("owner_user_name", ""),
        } for s in spaces]
    except Exception as exc:
        st.warning(f"Could not fetch Genie spaces: {exc}")
        return []


# ---------------------------------------------------------------------------
# 9. Genie usage
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_genie_usage(days: int = 30) -> pd.DataFrame:
    """Return per-space Genie usage from system.ai_gateway.usage.

    The AI Gateway logs Genie conversation traffic with destination_type
    containing 'GENIE' (or requester_type = 'GENIE' for outbound calls).
    We filter broadly so that spaces that route via AI Gateway are captured.

    If no rows match (e.g. Genie traffic is not yet flowing through AI
    Gateway in this workspace), we fall back to the Genie space list so
    the Genie tab still shows the space directory with zero-query counts.
    """
    sql = f"""
    SELECT
        endpoint_name,
        COALESCE(destination_name, endpoint_name, 'unknown') AS space_name,
        COUNT(*)                                    AS queries,
        COUNT(DISTINCT requester)                   AS users,
        SUM(total_tokens)                           AS tokens
    FROM system.ai_gateway.usage
    WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
      AND (
          UPPER(destination_type)  LIKE '%GENIE%'
          OR UPPER(requester_type) LIKE '%GENIE%'
          OR LOWER(endpoint_name)  LIKE '%genie%'
          OR LOWER(api_type)       LIKE '%genie%'
      )
    GROUP BY 1, 2
    ORDER BY queries DESC
    """
    df = _run_query(sql)

    # Fallback: if no AI Gateway usage rows, build a skeleton from the
    # Genie space list so callers always get a usable DataFrame.
    if df.empty:
        spaces = get_genie_spaces()
        if spaces:
            df = pd.DataFrame([
                {
                    "endpoint_name": s.get("id", ""),
                    "space_name":    s.get("title", "Unnamed"),
                    "queries":       0,
                    "users":         0,
                    "tokens":        0,
                }
                for s in spaces
            ])
    return df


# ---------------------------------------------------------------------------
# 10. AI Gateway endpoint configs (SDK serving_endpoints)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_endpoint_configs() -> list[dict]:
    """Return AI Gateway endpoint config objects via the SDK.

    serving_endpoints.list() returns lightweight ServingEndpoint objects
    (which include the ai_gateway field from the SDK's ServingEndpoint
    dataclass). Each endpoint is converted to a plain dict with governance
    booleans so app.py can render compliance cards and tables without
    importing SDK types.
    """
    client = get_client()
    try:
        endpoints = list(client.serving_endpoints.list())
        result = []
        for ep in endpoints:
            # state.ready is an EndpointStateReady enum; use .value for the
            # string representation, with a safe fallback.
            ready_val = "UNKNOWN"
            if ep.state and ep.state.ready is not None:
                ready_val = ep.state.ready.value

            ep_dict: dict[str, Any] = {
                "name":                    ep.name or "",
                "state":                   ready_val,
                "creator":                 ep.creator or "",
                "creation_timestamp":      ep.creation_timestamp,
                "last_updated_timestamp":  ep.last_updated_timestamp,
                # Governance flags — default False until confirmed present
                "guardrails_enabled":      False,
                "rate_limits_configured":  False,
                "usage_tracking_enabled":  False,
            }

            if ep.ai_gateway:
                gw = ep.ai_gateway
                ep_dict["guardrails_enabled"] = gw.guardrails is not None
                ep_dict["rate_limits_configured"] = bool(gw.rate_limits)
                ep_dict["usage_tracking_enabled"] = (
                    gw.usage_tracking_config.enabled
                    if gw.usage_tracking_config
                    else False
                )

            result.append(ep_dict)
        return result
    except Exception as exc:
        st.warning(f"Could not fetch endpoint configs: {exc}")
        return []


# ---------------------------------------------------------------------------
# 11. Monthly cost breakdown from system.billing.usage
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_monthly_cost(months: int = 6) -> pd.DataFrame:
    sql = f"""
    SELECT
        DATE_TRUNC('MONTH', usage_date)             AS month,
        SUM(CASE
            WHEN sku_name LIKE '%MODEL_SERVING%'
              OR sku_name LIKE '%INFERENCE%'
            THEN usage_quantity ELSE 0
        END)                                        AS model_serving_dbus,
        SUM(CASE
            WHEN sku_name LIKE '%AI_GATEWAY%'
            THEN usage_quantity ELSE 0
        END)                                        AS ai_gateway_dbus,
        SUM(CASE
            WHEN sku_name LIKE '%AI_FUNCTION%'
              OR sku_name LIKE '%SQL_AI%'
            THEN usage_quantity ELSE 0
        END)                                        AS ai_functions_dbus
    FROM system.billing.usage
    WHERE usage_date >= ADD_MONTHS(CURRENT_DATE(), -{months})
      AND (
          sku_name LIKE '%MODEL_SERVING%'
          OR sku_name LIKE '%INFERENCE%'
          OR sku_name LIKE '%AI_GATEWAY%'
          OR sku_name LIKE '%AI_FUNCTION%'
          OR sku_name LIKE '%SQL_AI%'
      )
    GROUP BY 1
    ORDER BY 1
    """
    df = _run_query(sql)
    if not df.empty and "month" in df.columns:
        df["month"] = pd.to_datetime(df["month"])
    return df


# ---------------------------------------------------------------------------
# 12. Cost by model (estimated from token usage)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_cost_by_model(days: int = 30) -> pd.DataFrame:
    sql = f"""
    SELECT
        COALESCE(destination_model, 'unknown')                  AS destination_model,
        SUM(total_tokens) * {_TOKEN_TO_DBU}                     AS estimated_dbus,
        SUM(total_tokens) * {_TOKEN_TO_DBU} * {_DBU_COST_USD}  AS estimated_cost_usd
    FROM system.ai_gateway.usage
    WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
    GROUP BY 1
    ORDER BY estimated_dbus DESC
    """
    return _run_query(sql)


# ---------------------------------------------------------------------------
# 13. Guardrail / content-filter events
# AI Gateway returns HTTP 403 for guardrail-blocked requests.
# request_tags is a MAP<STRING,STRING> — to_json() converts it to a JSON
# string for LIKE matching. endpoint_metadata is a STRUCT; we use
# to_json() on it similarly. The non-existent invocation_metadata column
# has been removed.
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_guardrail_events(days: int = 30) -> pd.DataFrame:
    sql = f"""
    SELECT
        CAST(event_time AS DATE)                            AS date,
        SUM(CASE WHEN status_code = 403 THEN 1 ELSE 0 END) AS blocked_count,
        SUM(CASE
            WHEN to_json(request_tags) LIKE '%pii%'
              OR to_json(request_tags) LIKE '%PII%'
            THEN 1 ELSE 0
        END)                                                AS pii_triggers,
        SUM(CASE
            WHEN to_json(request_tags)   LIKE '%safety%'
              OR to_json(request_tags)   LIKE '%blocked%'
              OR to_json(endpoint_tags)  LIKE '%safety%'
            THEN 1 ELSE 0
        END)                                                AS safety_triggers
    FROM system.ai_gateway.usage
    WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
    GROUP BY 1
    ORDER BY 1
    """
    df = _run_query(sql)
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


# ---------------------------------------------------------------------------
# 14. Rate-limit events (HTTP 429)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_rate_limit_events(days: int = 30) -> pd.DataFrame:
    sql = f"""
    SELECT
        CAST(event_time AS DATE)                            AS date,
        COALESCE(endpoint_name, 'unknown')                  AS endpoint,
        COUNT(*)                                            AS rate_limited_count
    FROM system.ai_gateway.usage
    WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
      AND status_code = 429
    GROUP BY 1, 2
    ORDER BY 1, rate_limited_count DESC
    """
    df = _run_query(sql)
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


# ---------------------------------------------------------------------------
# 15. Access audit log — AI-related actions
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_access_audit_ai(days: int = 30) -> pd.DataFrame:
    """Use system.access.assistant_events (available on this workspace).
    Columns: account_id, workspace_id, event_id, event_time, event_date,
             user_agent, initiated_by
    """
    sql = f"""
    SELECT
        event_date                                          AS date,
        COALESCE(initiated_by, 'unknown')                   AS user,
        COUNT(*)                                            AS count
    FROM system.access.assistant_events
    WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
    GROUP BY 1, 2
    ORDER BY 1 DESC, count DESC
    LIMIT 200
    """
    df = _run_query(sql)
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


# ---------------------------------------------------------------------------
# Group attribution — map users to Databricks groups then aggregate usage
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def get_user_group_map() -> dict:
    """Return {email: [group_display_name, ...]} by looking up each active user's groups.

    More efficient than enumerating all groups (dogfood has 49K+ empty groups).
    Gets the top 200 active users from AI Gateway, then looks up their group memberships.
    """
    # Get active users from last 30 days
    active_df = _run_query("""
        SELECT DISTINCT LOWER(requester) AS email
        FROM system.ai_gateway.usage
        WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL 30 DAYS
          AND requester LIKE '%@%'
        LIMIT 200
    """)
    if active_df.empty:
        return {}

    host = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
    try:
        obo_token = st.context.headers.get("X-Forwarded-Access-Token", "")
    except Exception:
        obo_token = ""

    if obo_token and host:
        client = WorkspaceClient(host=host, token=obo_token)
    else:
        client = _get_cached_client()

    user_groups: dict = {}
    for email in active_df["email"].tolist():
        try:
            users = list(client.users.list(filter=f"userName eq \"{email}\"", attributes="userName,groups"))
            for user in users:
                groups = [g.display for g in (user.groups or []) if g.display]
                if groups:
                    user_groups[email] = groups
        except Exception:
            continue
    return user_groups


@st.cache_data(ttl=300, show_spinner=False)
def get_usage_by_group(days: int = 30) -> pd.DataFrame:
    """Aggregate AI Gateway usage and estimated cost by Databricks group.

    Steps:
    1. Pull per-requester usage from system.ai_gateway.usage
    2. Join with group membership map
    3. Explode (users in multiple groups appear in each)
    4. Aggregate tokens + estimated cost by group

    Returns columns: group, members_active, requests, input_tokens,
                     output_tokens, total_tokens, est_cost_usd, pct_of_total
    """
    # Get raw per-user usage
    sql = f"""
    SELECT
        LOWER(requester)             AS user_email,
        requester_type,
        COUNT(*)                     AS requests,
        SUM(input_tokens)            AS input_tokens,
        SUM(output_tokens)           AS output_tokens,
        SUM(total_tokens)            AS total_tokens
    FROM system.ai_gateway.usage
    WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
      AND status_code = 200
    GROUP BY 1, 2
    ORDER BY total_tokens DESC
    """
    user_df = _run_query(sql)
    if user_df.empty:
        return pd.DataFrame()

    # Numeric coerce
    for col in ("requests", "input_tokens", "output_tokens", "total_tokens"):
        if col in user_df.columns:
            user_df[col] = pd.to_numeric(user_df[col], errors="coerce").fillna(0)

    # Fetch group membership
    user_group_map = get_user_group_map()

    # Assign groups — users with no group get "Ungrouped"
    rows = []
    for _, row in user_df.iterrows():
        email = str(row.get("user_email", "")).lower()
        groups = user_group_map.get(email) or ["Ungrouped / Service Principals"]
        for g in groups:
            rows.append({
                "group":         g,
                "user_email":    email,
                "requests":      row["requests"],
                "input_tokens":  row["input_tokens"],
                "output_tokens": row["output_tokens"],
                "total_tokens":  row["total_tokens"],
            })

    if not rows:
        return pd.DataFrame()

    expanded = pd.DataFrame(rows)
    grouped = expanded.groupby("group").agg(
        members_active=("user_email",  "nunique"),
        requests=       ("requests",    "sum"),
        input_tokens=   ("input_tokens","sum"),
        output_tokens=  ("output_tokens","sum"),
        total_tokens=   ("total_tokens","sum"),
    ).reset_index()

    # Estimated cost: blended ~$0.002 per 1K tokens (illustrative list-price)
    grouped["est_cost_usd"] = (grouped["total_tokens"] / 1_000 * 0.002).round(2)

    total_tokens = grouped["total_tokens"].sum()
    grouped["pct_of_total"] = (
        (grouped["total_tokens"] / total_tokens * 100).round(1)
        if total_tokens > 0 else 0
    )

    return grouped.sort_values("total_tokens", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner=False)
def get_top_users_in_group(group_name: str, days: int = 30) -> pd.DataFrame:
    """Return top users within a specific group."""
    user_group_map = get_user_group_map()
    members = [email for email, groups in user_group_map.items() if group_name in groups]
    if not members:
        return pd.DataFrame()

    placeholders = ", ".join(f"'{e}'" for e in members[:100])
    sql = f"""
    SELECT
        LOWER(requester)     AS user_email,
        COUNT(*)             AS requests,
        SUM(total_tokens)    AS total_tokens,
        ROUND(AVG(latency_ms), 0) AS avg_latency_ms,
        SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) AS rate_limited
    FROM system.ai_gateway.usage
    WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
      AND LOWER(requester) IN ({placeholders})
    GROUP BY 1
    ORDER BY total_tokens DESC
    LIMIT 20
    """
    return _run_query(sql)
