"""
config.py — AEMO AI Governance App
Central configuration: connection constants, brand palette, lookup dictionaries.
"""

# ---------------------------------------------------------------------------
# Databricks workspace
# ---------------------------------------------------------------------------
HOST = "e2-demo-field-eng.cloud.databricks.com"
ORG_ID = "1444828305810485"
WH_ID = "9d8a677b3c55b8a7"

# ---------------------------------------------------------------------------
# System tables
# ---------------------------------------------------------------------------
AI_GATEWAY_USAGE_TABLE = "system.ai_gateway.usage"
BILLING_USAGE_TABLE = "system.billing.usage"
AUDIT_TABLE = "system.access.audit"

# ---------------------------------------------------------------------------
# Genie
# ---------------------------------------------------------------------------
GENIE_API_BASE = "/api/2.0/genie/spaces"

# ---------------------------------------------------------------------------
# AEMO brand colours
# ---------------------------------------------------------------------------
COLOUR_NAVY = "#003A5C"       # primary dark navy — headers, sidebar
COLOUR_TEAL = "#00A651"       # primary teal — positive indicators, success
COLOUR_ACCENT = "#F5A623"     # amber accent — warnings / alerts
COLOUR_WHITE = "#FFFFFF"
COLOUR_LIGHT_GREY = "#F4F4F4"
COLOUR_MID_GREY = "#9E9E9E"
COLOUR_DARK_GREY = "#333333"
COLOUR_ERROR = "#D32F2F"      # red — errors / blocked requests

# Plotly-friendly palette list (ordered for sequential chart series)
CHART_PALETTE = [
    COLOUR_TEAL,
    COLOUR_NAVY,
    COLOUR_ACCENT,
    "#005B8E",   # mid-blue
    "#7BC8A4",   # light teal
    "#F9C55A",   # light amber
    COLOUR_MID_GREY,
]

# ---------------------------------------------------------------------------
# Model display names
# Databricks serving endpoint / foundation model identifiers → short labels
# ---------------------------------------------------------------------------
MODEL_DISPLAY_NAMES: dict[str, str] = {
    # Llama 3.x family
    "databricks-meta-llama-3-3-70b-instruct": "Llama 3.3 70B",
    "databricks-meta-llama-3-1-70b-instruct": "Llama 3.1 70B",
    "databricks-meta-llama-3-1-8b-instruct": "Llama 3.1 8B",
    "databricks-meta-llama-3-70b-instruct": "Llama 3 70B",
    "databricks-meta-llama-3-8b-instruct": "Llama 3 8B",
    # Mixtral / DBRX
    "databricks-mixtral-8x7b-instruct": "Mixtral 8x7B",
    "databricks-dbrx-instruct": "DBRX Instruct",
    # External / provisioned throughput
    "databricks-claude-sonnet-4": "Claude Sonnet 4",
    "databricks-claude-3-5-sonnet": "Claude 3.5 Sonnet",
    "databricks-claude-3-haiku": "Claude 3 Haiku",
    "databricks-gpt-4o": "GPT-4o",
    "databricks-gpt-4o-mini": "GPT-4o Mini",
    # Embedding models
    "databricks-gte-large-en": "GTE Large (EN)",
    "databricks-bge-large-en": "BGE Large (EN)",
    "databricks-bge-m3": "BGE M3",
}

def get_model_label(model_id: str | None) -> str:
    """Return a human-readable model name, falling back to the raw ID."""
    if model_id is None:
        return "Unknown"
    return MODEL_DISPLAY_NAMES.get(model_id, model_id)


# ---------------------------------------------------------------------------
# Requester type labels
# Maps the string values stored in system.ai_gateway.usage.requester_type
# ---------------------------------------------------------------------------
REQUESTER_TYPE_LABELS: dict[str, str] = {
    "SERVICE_PRINCIPAL": "Service Principal",
    "USER": "User",
    "NOTEBOOK": "Notebook",
    "JOB": "Job / Workflow",
    "PIPELINE": "Delta Live Tables Pipeline",
    "MODEL_SERVING": "Model Serving Endpoint",
    "GENIE": "Genie Space",
    "AGENT": "AI Agent",
    "UNKNOWN": "Unknown",
}

def get_requester_type_label(rtype: str | None) -> str:
    if rtype is None:
        return "Unknown"
    return REQUESTER_TYPE_LABELS.get(rtype, rtype.replace("_", " ").title())


# ---------------------------------------------------------------------------
# HTTP status code labels
# Covers the range returned by FMAPI / AI Gateway
# ---------------------------------------------------------------------------
STATUS_CODE_LABELS: dict[int, str] = {
    200: "Success",
    400: "Bad Request",
    401: "Unauthorised",
    403: "Forbidden",
    404: "Not Found",
    408: "Request Timeout",
    429: "Rate Limited",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}

def get_status_label(code: int | None) -> str:
    if code is None:
        return "Unknown"
    return STATUS_CODE_LABELS.get(code, f"HTTP {code}")

def is_error_status(code: int | None) -> bool:
    return code is not None and code >= 400

def is_guardrail_status(code: int | None) -> bool:
    """AI Gateway returns 403 for guardrail-blocked requests."""
    return code == 403


# ---------------------------------------------------------------------------
# Time-window filter options
# Each entry: (display label, SQL interval string, pandas timedelta days)
# ---------------------------------------------------------------------------
TIME_WINDOWS: list[dict] = [
    {"label": "Last 24 hours", "sql_interval": "INTERVAL 1 DAY",  "days": 1},
    {"label": "Last 7 days",   "sql_interval": "INTERVAL 7 DAYS", "days": 7},
    {"label": "Last 14 days",  "sql_interval": "INTERVAL 14 DAYS","days": 14},
    {"label": "Last 30 days",  "sql_interval": "INTERVAL 30 DAYS","days": 30},
    {"label": "Last 90 days",  "sql_interval": "INTERVAL 90 DAYS","days": 90},
]
DEFAULT_TIME_WINDOW_INDEX = 2  # Last 30 days

def get_time_window(label: str) -> dict:
    """Look up a time window dict by display label."""
    for tw in TIME_WINDOWS:
        if tw["label"] == label:
            return tw
    return TIME_WINDOWS[DEFAULT_TIME_WINDOW_INDEX]


# ---------------------------------------------------------------------------
# Cost estimation constants
# Approximate list-price rates for token cost attribution in the Overview tab.
# All figures in USD per 1 000 tokens. Update when pricing changes.
# ---------------------------------------------------------------------------
TOKEN_COST_PER_1K: dict[str, dict[str, float]] = {
    "databricks-meta-llama-3-3-70b-instruct": {"input": 0.00054, "output": 0.00162},
    "databricks-meta-llama-3-1-70b-instruct": {"input": 0.00054, "output": 0.00162},
    "databricks-meta-llama-3-1-8b-instruct":  {"input": 0.00010, "output": 0.00030},
    "databricks-dbrx-instruct":               {"input": 0.00075, "output": 0.00225},
    "databricks-mixtral-8x7b-instruct":       {"input": 0.00045, "output": 0.00045},
    # External models — indicative only
    "databricks-claude-sonnet-4":             {"input": 0.00300, "output": 0.01500},
    "databricks-claude-3-5-sonnet":           {"input": 0.00300, "output": 0.01500},
    "databricks-claude-3-haiku":              {"input": 0.00025, "output": 0.00125},
    "databricks-gpt-4o":                      {"input": 0.00250, "output": 0.01000},
    "databricks-gpt-4o-mini":                 {"input": 0.00015, "output": 0.00060},
}
DEFAULT_TOKEN_COST = {"input": 0.00050, "output": 0.00150}  # fallback

def estimate_cost_usd(
    model_id: str | None,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Return an estimated USD cost for a single request."""
    rates = TOKEN_COST_PER_1K.get(model_id or "", DEFAULT_TOKEN_COST)
    return (input_tokens / 1000 * rates["input"]) + (output_tokens / 1000 * rates["output"])


# ---------------------------------------------------------------------------
# Latency thresholds (milliseconds) — used for colouring the latency chart
# ---------------------------------------------------------------------------
LATENCY_OK_MS = 2_000      # green
LATENCY_WARN_MS = 5_000    # amber
# anything above LATENCY_WARN_MS → red (COLOUR_ERROR)

# ---------------------------------------------------------------------------
# Guardrail / policy labels
# Mirrors AI Gateway guardrail type identifiers where available
# ---------------------------------------------------------------------------
GUARDRAIL_TYPE_LABELS: dict[str, str] = {
    "PII_DETECTION":     "PII Detection",
    "TOXICITY":          "Toxicity Filter",
    "PROMPT_INJECTION":  "Prompt Injection",
    "TOPIC_RESTRICTION": "Topic Restriction",
    "CUSTOM_PATTERN":    "Custom Pattern",
    "RATE_LIMIT":        "Rate Limit",
}

# ---------------------------------------------------------------------------
# App metadata
# ---------------------------------------------------------------------------
APP_TITLE = "AEMO AI Governance"
APP_ICON = ":shield:"   # Streamlit page icon
APP_SUBTITLE = "Foundation Model & AI Gateway usage, cost, and policy dashboard"
APP_VERSION = "0.1.0"
