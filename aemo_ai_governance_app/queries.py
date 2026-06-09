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

@st.cache_resource
def get_client() -> WorkspaceClient:
    """Return a cached WorkspaceClient.

    In a Databricks Apps runtime (DATABRICKS_RUNTIME_ENV is set by the
    platform) we call WorkspaceClient() with no arguments — the SDK reads
    DATABRICKS_HOST and the OAuth token automatically.

    Locally, fall back to the named profile so developers can run the app
    without touching environment variables.
    """
    if os.environ.get("DATABRICKS_RUNTIME_ENV"):
        # Running inside a Databricks App — use ambient OAuth credentials
        return WorkspaceClient()
    # Local development — use the named profile
    return WorkspaceClient(profile="e2-demo-west")


WAREHOUSE_ID = "9d8a677b3c55b8a7"

# Cost constants (approximate list-price DBU rates; adjust to contract rates)
_DBU_COST_USD = 0.07          # Model Serving / AI Gateway DBU → USD (rough)
_TOKEN_TO_DBU = 1 / 1_000_000  # 1 DBU ≈ 1 M tokens (illustrative)


# ---------------------------------------------------------------------------
# SDK statement execution helper
# ---------------------------------------------------------------------------

def _run_query(sql: str, timeout_secs: int = 60) -> pd.DataFrame:
    """Execute SQL via SDK statement execution and return a DataFrame.

    Returns an empty DataFrame on error so callers degrade gracefully.
    """
    client = get_client()
    try:
        resp = client.statement_execution.execute_statement(
            warehouse_id=WAREHOUSE_ID,
            statement=sql,
            wait_timeout=f"{timeout_secs}s",
        )

        # Poll if still running (SDK wait_timeout should handle this, but be safe)
        deadline = time.time() + timeout_secs
        while resp.status.state in (
            StatementState.PENDING,
            StatementState.RUNNING,
        ):
            if time.time() > deadline:
                raise TimeoutError("Query exceeded timeout")
            time.sleep(1)
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
        resp = client.genie.list_spaces()
        spaces = resp.spaces or []
        result = []
        for space in spaces:
            result.append({
                "id":          space.space_id or "",
                "title":       space.title or space.space_id or "Unnamed",
                "description": space.description or "",
                "warehouse_id": space.warehouse_id or "",
                # owner_user_name / creator not returned by list_spaces —
                # set a placeholder; could be fetched per-space if needed
                "owner_user_name": "",
            })
        return result
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
    sql = f"""
    SELECT
        CAST(event_time AS DATE)                            AS date,
        action_name                                         AS action,
        COALESCE(user_identity.email, 'unknown')            AS user,
        COUNT(*)                                            AS count
    FROM system.access.audit
    WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
      AND (
          service_name IN (
              'modelServing', 'aiGateway', 'vectorSearch',
              'genie', 'aiPlayground', 'databricksSql'
          )
          OR action_name LIKE '%Model%'
          OR action_name LIKE '%Endpoint%'
          OR action_name LIKE '%Genie%'
          OR action_name LIKE '%AI%'
      )
    GROUP BY 1, 2, 3
    ORDER BY 1 DESC, count DESC
    """
    df = _run_query(sql)
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df
