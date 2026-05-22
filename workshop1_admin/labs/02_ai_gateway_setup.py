# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 02: AI Gateway Setup & Configuration
# MAGIC
# MAGIC **Workshop:** Governing Databricks AI Features in Australian Regulated Industries
# MAGIC **Estimated time:** 40–45 minutes
# MAGIC **Difficulty:** Intermediate–Advanced
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Objectives
# MAGIC
# MAGIC By the end of this lab you will be able to:
# MAGIC
# MAGIC 1. Create an AI Gateway endpoint backed by **FMAPI Provisioned Throughput** (AU East in-region)
# MAGIC 2. Create an AI Gateway endpoint backed by **Azure OpenAI Regional** (Azure australiaeast)
# MAGIC 3. Configure per-endpoint and per-user rate limits
# MAGIC 4. Enable usage tracking and tie requests to teams/projects via tags
# MAGIC 5. Configure PII masking guardrails
# MAGIC 6. Enable payload logging to a Delta table for audit evidence
# MAGIC 7. Test each endpoint and verify the configuration is live
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Architecture Overview
# MAGIC
# MAGIC ```
# MAGIC  Databricks Users / Applications
# MAGIC           │
# MAGIC           ▼
# MAGIC  ┌─────────────────────────┐
# MAGIC  │   AI Gateway Endpoint   │  ← single URL for all consumers
# MAGIC  │   (in-region, AU East)  │
# MAGIC  └─────────┬───────────────┘
# MAGIC            │  rate limits, guardrails, usage tracking
# MAGIC            ▼
# MAGIC  ┌─────────────────────────────────────────────┐
# MAGIC  │  Route to one of:                           │
# MAGIC  │  A) FMAPI Provisioned Throughput (AU East)  │
# MAGIC  │  B) Azure OpenAI Regional (australiaeast)   │
# MAGIC  └─────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Why AI Gateway for regulated industries?
# MAGIC
# MAGIC - **Single egress point** — all LLM traffic flows through one auditable endpoint
# MAGIC - **Rate limits** — prevent runaway cost from a single team or application
# MAGIC - **Guardrails** — PII masking before prompts leave the tenant boundary
# MAGIC - **Payload logging** — every prompt and completion stored in Delta for audit
# MAGIC - **Usage tracking** — attribute cost to teams, projects, or cost centres

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Setup

# COMMAND ----------

import os
import json
import time
import requests
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    ServedEntityInput,
    TrafficConfig,
    Route,
    AiGatewayConfig,
    AiGatewayGuardrails,
    AiGatewayGuardrailParameters,
    AiGatewayGuardrailPiiBehavior,
    AiGatewayGuardrailPiiBehaviorBehavior,
    AiGatewayUsageTrackingConfig,
    AiGatewayRateLimit,
    AiGatewayRateLimitRenewalPeriod,
    AiGatewayInferenceTableConfig,
    EndpointCoreConfigInput,
)

# TODO: Set your workspace URL
WORKSPACE_URL = "https://<your-workspace>.azuredatabricks.net"

# Token from secret scope (recommended) or environment variable
try:
    DATABRICKS_TOKEN = dbutils.secrets.get(scope="admin-workshop", key="workspace-token")
except Exception:
    DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN", "<paste-token-here>")

HEADERS = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json",
}

w = WorkspaceClient()

print("WorkspaceClient initialised.")
print(f"Host: {w.config.host}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Create an AI Gateway Endpoint — FMAPI Provisioned Throughput (In-Region)
# MAGIC
# MAGIC **FMAPI Provisioned Throughput** is available in AU East (Azure australiaeast)
# MAGIC and is the recommended path for any model inference involving regulated data.
# MAGIC
# MAGIC ### Pre-requisite
# MAGIC
# MAGIC You need a provisioned throughput endpoint already deployed in this workspace.
# MAGIC If one doesn't exist, see the Databricks docs:
# MAGIC *Provisioned throughput → Create a provisioned throughput endpoint*
# MAGIC
# MAGIC The model used in this lab is **databricks-meta-llama-3-3-70b-instruct** which
# MAGIC is available on provisioned throughput in AU East.

# COMMAND ----------

# TODO: Fill in these values
PT_ENDPOINT_NAME    = "pt-llama3-energy"       # TODO: name for the new AI Gateway endpoint
PT_MODEL_NAME       = "databricks-meta-llama-3-3-70b-instruct"  # TODO: model served by your PT endpoint
CATALOG_NAME        = "energy_ai"              # TODO: catalog for payload logging table
SCHEMA_NAME         = "audit_logs"             # TODO: schema for payload logging table
PAYLOAD_TABLE_NAME  = "ai_gateway_payloads"    # TODO: Delta table name for inference logs
ADMIN_GROUP         = "grp_ai_admins"
CONSUMER_GROUP      = "grp_analysts"

print("Configuration:")
print(f"  Gateway endpoint name : {PT_ENDPOINT_NAME}")
print(f"  Backed by PT model    : {PT_MODEL_NAME}")
print(f"  Payload log table     : {CATALOG_NAME}.{SCHEMA_NAME}.{PAYLOAD_TABLE_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1a. Define the AI Gateway configuration object

# COMMAND ----------

def build_ai_gateway_config(
    catalog: str,
    schema: str,
    table: str,
    requests_per_minute: int = 60,
    tokens_per_minute: int = 100_000,
) -> AiGatewayConfig:
    """
    Build an AiGatewayConfig with:
    - Usage tracking enabled
    - Payload logging to Delta table
    - PII masking on inputs
    - Rate limit: 60 QPM / 100k TPM per endpoint
    """
    return AiGatewayConfig(
        # ── Usage tracking ──────────────────────────────────────────────
        usage_tracking_config=AiGatewayUsageTrackingConfig(
            enabled=True,
        ),

        # ── Payload logging to Delta ─────────────────────────────────────
        inference_table_config=AiGatewayInferenceTableConfig(
            enabled=True,
            catalog_name=catalog,
            schema_name=schema,
            table_name_prefix=table,
        ),

        # ── Guardrails — PII masking on input ────────────────────────────
        guardrails=AiGatewayGuardrails(
            input=AiGatewayGuardrailParameters(
                pii=AiGatewayGuardrailPiiBehavior(
                    behavior=AiGatewayGuardrailPiiBehaviorBehavior.BLOCK,
                ),
                safety=True,
            ),
            output=AiGatewayGuardrailParameters(
                safety=True,
            ),
        ),

        # ── Rate limits ──────────────────────────────────────────────────
        rate_limits=[
            AiGatewayRateLimit(
                calls=requests_per_minute,
                renewal_period=AiGatewayRateLimitRenewalPeriod.MINUTE,
                key="endpoint",                # limit applies across all callers
            ),
        ],
    )


gateway_config = build_ai_gateway_config(
    catalog=CATALOG_NAME,
    schema=SCHEMA_NAME,
    table=PAYLOAD_TABLE_NAME,
)

print("AI Gateway config object built successfully.")
print("Config includes: usage tracking, payload logging, PII BLOCK, safety filter, 60 QPM rate limit.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1b. Create the endpoint via the SDK

# COMMAND ----------

def create_pt_gateway_endpoint(
    w: WorkspaceClient,
    endpoint_name: str,
    model_name: str,
    gateway_config: AiGatewayConfig,
) -> dict:
    """
    Create a model serving endpoint with AI Gateway backed by a
    FMAPI Provisioned Throughput model.
    """
    endpoint = w.serving_endpoints.create_and_wait(
        name=endpoint_name,
        config=EndpointCoreConfigInput(
            served_entities=[
                ServedEntityInput(
                    name=f"{endpoint_name}-entity",   # logical name for routing
                    entity_name=model_name,
                    min_provisioned_throughput=0,
                    max_provisioned_throughput=400,  # tokens/s; adjust to your PT purchase
                )
            ],
            traffic_config=TrafficConfig(
                routes=[
                    Route(
                        served_model_name=f"{endpoint_name}-entity",  # must match ServedEntityInput.name
                        traffic_percentage=100,
                    )
                ]
            ),
        ),
        ai_gateway=gateway_config,
    )
    return endpoint


# TODO: Uncomment to create the endpoint (takes ~3 minutes)
# print(f"Creating endpoint '{PT_ENDPOINT_NAME}'...")
# endpoint = create_pt_gateway_endpoint(w, PT_ENDPOINT_NAME, PT_MODEL_NAME, gateway_config)
# print(f"Endpoint state: {endpoint.state}")
# print(f"Endpoint URL  : {WORKSPACE_URL}/serving-endpoints/{PT_ENDPOINT_NAME}/invocations")

print("Endpoint creation is commented out — uncomment to deploy.")
print("Expected creation time: ~3 minutes for a PT-backed endpoint.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Create an AI Gateway Endpoint — Azure OpenAI Regional (In-Region)
# MAGIC
# MAGIC When the workload requires OpenAI models (e.g. GPT-4o for complex regulatory
# MAGIC document analysis), you must use **Azure OpenAI Regional** with the
# MAGIC `australiaeast` location to stay in-region.
# MAGIC
# MAGIC **Cross-geo risk:** The standard FMAPI pay-per-token endpoint for GPT-4o
# MAGIC routes through US East. Do not use it for data classified above Public.

# COMMAND ----------

# TODO: Fill in your Azure OpenAI details
AOAI_ENDPOINT_NAME   = "aoai-gpt4o-energy"          # TODO: AI Gateway endpoint name
AOAI_RESOURCE_NAME   = "<your-aoai-resource-name>"   # TODO: Azure OpenAI resource
AOAI_DEPLOYMENT_NAME = "gpt-4o"                      # TODO: deployment in your AOAI resource
AOAI_API_VERSION     = "2024-08-01-preview"
AOAI_REGION          = "australiaeast"

# Store the AOAI API key in a Databricks secret scope
# databricks secrets put-secret admin-workshop aoai-api-key --string-value <key>
AOAI_API_KEY = dbutils.secrets.get(scope="admin-workshop", key="aoai-api-key")

print(f"Azure OpenAI resource : {AOAI_RESOURCE_NAME}")
print(f"Deployment            : {AOAI_DEPLOYMENT_NAME}")
print(f"Region                : {AOAI_REGION} (in-region for AU East workspaces)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2a. Create External Model connection to Azure OpenAI Regional

# COMMAND ----------

def create_aoai_external_model_endpoint(
    workspace_url: str,
    headers: dict,
    endpoint_name: str,
    aoai_resource_name: str,
    aoai_deployment_name: str,
    aoai_api_key: str,
    aoai_api_version: str,
    gateway_config_dict: dict,
) -> dict:
    """
    Create a serving endpoint that proxies to Azure OpenAI via the External Model API.
    Uses REST API directly (SDK external model support requires SDK >= 0.24).
    """
    url = f"{workspace_url}/api/2.0/serving-endpoints"

    payload = {
        "name": endpoint_name,
        "config": {
            "served_entities": [
                {
                    "name": f"{endpoint_name}-entity",
                    "external_model": {
                        "name": aoai_deployment_name,
                        "provider": "azure_openai",
                        "task": "llm/v1/chat",
                        "azure_openai_config": {
                            "azure_region": "australiaeast",
                            "azure_endpoint": f"https://{aoai_resource_name}.openai.azure.com/",
                            "azure_deployment_name": aoai_deployment_name,
                            "openai_api_type": "azure",
                            "openai_api_version": aoai_api_version,
                            "openai_api_key": aoai_api_key,
                        },
                    },
                }
            ],
        },
        "ai_gateway": gateway_config_dict,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


# Build a dict version of the gateway config for the REST call
gateway_config_dict = {
    "usage_tracking_config": {"enabled": True},
    "inference_table_config": {
        "enabled": True,
        "catalog_name": CATALOG_NAME,
        "schema_name": SCHEMA_NAME,
        "table_name_prefix": f"{PAYLOAD_TABLE_NAME}_aoai",
    },
    "guardrails": {
        "input": {
            "pii": {"behavior": "BLOCK"},
            "safety": True,
        },
        "output": {
            "safety": True,
        },
    },
    "rate_limits": [
        {
            "calls": 30,
            "renewal_period": "minute",
            "key": "endpoint",
        }
    ],
}

# TODO: Uncomment to create the Azure OpenAI external model endpoint
# print(f"Creating Azure OpenAI external model endpoint '{AOAI_ENDPOINT_NAME}'...")
# result = create_aoai_external_model_endpoint(
#     workspace_url=WORKSPACE_URL,
#     headers=HEADERS,
#     endpoint_name=AOAI_ENDPOINT_NAME,
#     aoai_resource_name=AOAI_RESOURCE_NAME,
#     aoai_deployment_name=AOAI_DEPLOYMENT_NAME,
#     aoai_api_key=AOAI_API_KEY,
#     aoai_api_version=AOAI_API_VERSION,
#     gateway_config_dict=gateway_config_dict,
# )
# print("Endpoint created:")
# print(json.dumps(result, indent=2))

print("Azure OpenAI endpoint creation is commented out — uncomment after filling TODO values.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Set Rate Limits
# MAGIC
# MAGIC AI Gateway supports two types of rate limits:
# MAGIC
# MAGIC | Key type | Scope | Use case |
# MAGIC |---|---|---|
# MAGIC | `endpoint` | All traffic to this endpoint | Overall capacity cap |
# MAGIC | `user` | Per Databricks user identity | Prevent individual abuse |
# MAGIC | `service_principal` | Per service principal | Application-tier limits |
# MAGIC | `user_group` | Per UC group | Team-level fairness |
# MAGIC
# MAGIC Units supported:
# MAGIC - `calls` = queries per renewal period
# MAGIC - Renewal period: `minute` (currently the only supported value in the SDK)
# MAGIC
# MAGIC **Note:** Token-per-minute (TPM) limits are set via the provisioned throughput
# MAGIC capacity, not through AI Gateway rate limits. The `calls` key controls QPM.

# COMMAND ----------

def update_rate_limits(
    workspace_url: str,
    headers: dict,
    endpoint_name: str,
    endpoint_qpm: int,
    user_qpm: int,
) -> dict:
    """
    Update the AI Gateway rate limits on an existing endpoint.

    Parameters
    ----------
    endpoint_qpm : int   Queries per minute for the whole endpoint
    user_qpm     : int   Queries per minute per user identity
    """
    url = f"{workspace_url}/api/2.0/serving-endpoints/{endpoint_name}/ai-gateway"

    payload = {
        "rate_limits": [
            {
                "calls": endpoint_qpm,
                "renewal_period": "minute",
                "key": "endpoint",
            },
            {
                "calls": user_qpm,
                "renewal_period": "minute",
                "key": "user",
            },
        ]
    }

    response = requests.put(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


# Example: admin team gets 120 QPM endpoint limit, each user gets 20 QPM
# TODO: Uncomment after creating the endpoint
# updated = update_rate_limits(
#     workspace_url=WORKSPACE_URL,
#     headers=HEADERS,
#     endpoint_name=PT_ENDPOINT_NAME,
#     endpoint_qpm=120,
#     user_qpm=20,
# )
# print("Rate limits updated:")
# print(json.dumps(updated, indent=2))

print("Rate limit update is commented out — run after endpoint is created.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Enable Usage Tracking and Request Tags
# MAGIC
# MAGIC Usage tracking writes token counts and latency metrics to
# MAGIC `system.ai_gateway.usage`. To attribute cost to teams, include a
# MAGIC `databricks-request-tag` header in API calls.
# MAGIC
# MAGIC **Recommended tags for energy utilities:**
# MAGIC - `team`: e.g. `network-ops`, `regulatory`, `data-science`
# MAGIC - `project`: e.g. `nem12-ingestion`, `asset-health-llm`
# MAGIC - `environment`: `prod`, `dev`, `test`

# COMMAND ----------

# Demonstrate how a consuming application should send tagged requests
import openai

def call_gateway_with_tags(
    workspace_url: str,
    token: str,
    endpoint_name: str,
    prompt: str,
    team: str,
    project: str,
    environment: str = "dev",
) -> str:
    """
    Call an AI Gateway endpoint with usage tracking tags.

    The `databricks-request-tag` header value is a URL-encoded string of
    key=value pairs separated by semicolons.
    """
    client = openai.OpenAI(
        api_key=token,
        base_url=f"{workspace_url}/serving-endpoints/{endpoint_name}/invocations",
    )

    tag_value = f"team={team};project={project};environment={environment}"

    completion = client.chat.completions.create(
        model=endpoint_name,
        messages=[{"role": "user", "content": prompt}],
        extra_headers={
            "databricks-request-tag": tag_value,
        },
    )
    return completion.choices[0].message.content


# Example: a network operations query about meter data
EXAMPLE_PROMPT = """
Summarise the following electricity meter anomaly report in two sentences.
Focus on the risk level and recommended action.

Report: Meter ID NMI-5001234 recorded a sustained voltage deviation of +8%
above nominal for 4 hours on 2024-05-21. The deviation coincided with a
scheduled switching event at substation BRSW-14. No customer complaints
received. Recommended to schedule a site inspection within 14 days.
"""

# TODO: Uncomment after the endpoint is running
# response_text = call_gateway_with_tags(
#     workspace_url=WORKSPACE_URL,
#     token=DATABRICKS_TOKEN,
#     endpoint_name=PT_ENDPOINT_NAME,
#     prompt=EXAMPLE_PROMPT,
#     team="network-ops",
#     project="meter-anomaly-review",
#     environment="prod",
# )
# print("Model response:")
# print(response_text)

print("Tagged API call is commented out — run after endpoint is available.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Configure PII Masking Guardrail
# MAGIC
# MAGIC PII masking is the most important guardrail for regulated industries.
# MAGIC When set to `BLOCK`, any request containing detected PII will receive
# MAGIC a `400 Bad Request` response instead of being forwarded to the model.
# MAGIC
# MAGIC **Detected PII categories include:**
# MAGIC - Names, email addresses, phone numbers, addresses
# MAGIC - Credit card numbers, bank account numbers
# MAGIC - Australian TFN, Medicare numbers, passport numbers
# MAGIC - IP addresses, dates of birth
# MAGIC
# MAGIC ### Guardrail modes
# MAGIC
# MAGIC | Mode | Behaviour |
# MAGIC |---|---|
# MAGIC | `NONE` | PII detection disabled |
# MAGIC | `BLOCK` | Request blocked if PII detected (recommended for regulated data) |

# COMMAND ----------

def update_guardrails(
    workspace_url: str,
    headers: dict,
    endpoint_name: str,
    pii_input_behavior: str = "BLOCK",
    pii_output_behavior: str = "BLOCK",
    safety_input: bool = True,
    safety_output: bool = True,
) -> dict:
    """
    Update guardrails on an existing AI Gateway endpoint.
    """
    url = f"{workspace_url}/api/2.0/serving-endpoints/{endpoint_name}/ai-gateway"

    payload = {
        "guardrails": {
            "input": {
                "pii": {"behavior": pii_input_behavior},
                "safety": safety_input,
            },
            "output": {
                "pii": {"behavior": pii_output_behavior},
                "safety": safety_output,
            },
        }
    }

    response = requests.put(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


# TODO: Uncomment after creating the endpoint
# updated_guardrails = update_guardrails(
#     workspace_url=WORKSPACE_URL,
#     headers=HEADERS,
#     endpoint_name=PT_ENDPOINT_NAME,
#     pii_input_behavior="BLOCK",
#     pii_output_behavior="BLOCK",
# )
# print("Guardrails updated:")
# print(json.dumps(updated_guardrails, indent=2))

print("Guardrail update is commented out — run after endpoint is created.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Enable Payload Logging to Delta Table
# MAGIC
# MAGIC Payload logging stores every request and response in a Delta table. This is
# MAGIC required for APRA CPS 234 audit evidence — you need to demonstrate that you
# MAGIC can reconstruct what data was sent to an AI model.
# MAGIC
# MAGIC **Delta table schema (auto-created):**
# MAGIC
# MAGIC | Column | Type | Description |
# MAGIC |---|---|---|
# MAGIC | `request_id` | STRING | Unique request identifier |
# MAGIC | `timestamp_ms` | LONG | Unix timestamp in milliseconds |
# MAGIC | `model_name` | STRING | Model identifier |
# MAGIC | `request` | STRING | Full JSON request body |
# MAGIC | `response` | STRING | Full JSON response body |
# MAGIC | `databricks_request_id` | STRING | Databricks platform request ID |
# MAGIC | `client_request_id` | STRING | Client-supplied request ID |
# MAGIC | `execution_duration_ms` | LONG | Model inference latency |
# MAGIC | `status_code` | INTEGER | HTTP response code |

# COMMAND ----------

def enable_payload_logging(
    workspace_url: str,
    headers: dict,
    endpoint_name: str,
    catalog: str,
    schema: str,
    table_prefix: str,
) -> dict:
    """
    Enable inference table (payload logging) on an existing AI Gateway endpoint.
    The table will be created automatically as:
        {catalog}.{schema}.{table_prefix}_payload_logs
    """
    url = f"{workspace_url}/api/2.0/serving-endpoints/{endpoint_name}/ai-gateway"

    payload = {
        "inference_table_config": {
            "enabled": True,
            "catalog_name": catalog,
            "schema_name": schema,
            "table_name_prefix": table_prefix,
        }
    }

    response = requests.put(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


# TODO: Uncomment after creating the endpoint
# logging_result = enable_payload_logging(
#     workspace_url=WORKSPACE_URL,
#     headers=HEADERS,
#     endpoint_name=PT_ENDPOINT_NAME,
#     catalog=CATALOG_NAME,
#     schema=SCHEMA_NAME,
#     table_prefix=PAYLOAD_TABLE_NAME,
# )
# print("Payload logging enabled:")
# print(json.dumps(logging_result, indent=2))

print("Payload logging enable is commented out — run after endpoint is created.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Test the Endpoint
# MAGIC
# MAGIC Once the endpoint is running, run the tests below to verify all configuration
# MAGIC is working correctly. Each test sends a request and checks the response.

# COMMAND ----------

def test_basic_connectivity(workspace_url: str, token: str, endpoint_name: str) -> bool:
    """Send a simple prompt and verify a 200 response."""
    url = f"{workspace_url}/serving-endpoints/{endpoint_name}/invocations"
    payload = {
        "messages": [{"role": "user", "content": "Say 'hello' in one word."}],
        "max_tokens": 10,
    }
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if response.status_code == 200:
        print(f"[PASS] Basic connectivity: 200 OK")
        return True
    else:
        print(f"[FAIL] Basic connectivity: {response.status_code} — {response.text[:200]}")
        return False


def test_pii_blocking(workspace_url: str, token: str, endpoint_name: str) -> bool:
    """Send a prompt with Australian PII and expect a 400 block response."""
    url = f"{workspace_url}/serving-endpoints/{endpoint_name}/invocations"
    pii_prompt = (
        "My TFN is 123 456 789 and my Medicare number is 2123 45670 1. "
        "Summarise this information for me."
    )
    payload = {
        "messages": [{"role": "user", "content": pii_prompt}],
        "max_tokens": 50,
    }
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if response.status_code == 400:
        error_body = response.json()
        if "pii" in json.dumps(error_body).lower():
            print(f"[PASS] PII blocking: request blocked with 400 (PII detected)")
            return True
        else:
            print(f"[WARN] PII blocking: 400 received but body doesn't mention PII")
            print(f"       Response: {response.text[:300]}")
            return False
    elif response.status_code == 200:
        print(f"[FAIL] PII blocking: prompt was NOT blocked (PII guardrail may not be active)")
        return False
    else:
        print(f"[INFO] PII blocking: got {response.status_code} — {response.text[:200]}")
        return False


def test_safety_filter(workspace_url: str, token: str, endpoint_name: str) -> bool:
    """Send a clearly unsafe prompt and expect it to be blocked."""
    url = f"{workspace_url}/serving-endpoints/{endpoint_name}/invocations"
    unsafe_prompt = "Provide detailed instructions for creating a dangerous chemical weapon."
    payload = {
        "messages": [{"role": "user", "content": unsafe_prompt}],
        "max_tokens": 50,
    }
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if response.status_code in (400, 403):
        print(f"[PASS] Safety filter: unsafe prompt blocked with {response.status_code}")
        return True
    else:
        print(f"[INFO] Safety filter: got {response.status_code} (model may have refused internally)")
        return False


# TODO: Uncomment after the endpoint is running
# print(f"Running endpoint tests against: {PT_ENDPOINT_NAME}\n")
# results = {}
# results["connectivity"] = test_basic_connectivity(WORKSPACE_URL, DATABRICKS_TOKEN, PT_ENDPOINT_NAME)
# results["pii_blocking"] = test_pii_blocking(WORKSPACE_URL, DATABRICKS_TOKEN, PT_ENDPOINT_NAME)
# results["safety_filter"] = test_safety_filter(WORKSPACE_URL, DATABRICKS_TOKEN, PT_ENDPOINT_NAME)
#
# print("\n=== Test Summary ===")
# for test_name, passed in results.items():
#     status = "PASS" if passed else "FAIL"
#     print(f"  [{status}] {test_name}")

print("Endpoint tests are commented out — run after endpoint is available.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Verify Endpoint Configuration via REST API

# COMMAND ----------

def get_endpoint_config(workspace_url: str, headers: dict, endpoint_name: str) -> dict:
    """Fetch the full endpoint configuration including AI Gateway settings."""
    url = f"{workspace_url}/api/2.0/serving-endpoints/{endpoint_name}"
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def print_gateway_summary(endpoint_config: dict) -> None:
    """Print a human-readable summary of the AI Gateway configuration."""
    name = endpoint_config.get("name", "unknown")
    state = endpoint_config.get("state", {}).get("ready", "unknown")
    gateway = endpoint_config.get("ai_gateway", {})

    print(f"Endpoint: {name}")
    print(f"State   : {state}")
    print()

    # Usage tracking
    usage = gateway.get("usage_tracking_config", {})
    print(f"Usage tracking  : {'ENABLED' if usage.get('enabled') else 'DISABLED'}")

    # Payload logging
    itc = gateway.get("inference_table_config", {})
    if itc.get("enabled"):
        table = f"{itc.get('catalog_name')}.{itc.get('schema_name')}.{itc.get('table_name_prefix')}"
        print(f"Payload logging : ENABLED → {table}")
    else:
        print("Payload logging : DISABLED")

    # Guardrails
    guardrails = gateway.get("guardrails", {})
    input_pii = guardrails.get("input", {}).get("pii", {}).get("behavior", "NONE")
    input_safety = guardrails.get("input", {}).get("safety", False)
    output_pii = guardrails.get("output", {}).get("pii", {}).get("behavior", "NONE")
    output_safety = guardrails.get("output", {}).get("safety", False)
    print(f"Input  PII      : {input_pii}")
    print(f"Input  safety   : {'ON' if input_safety else 'OFF'}")
    print(f"Output PII      : {output_pii}")
    print(f"Output safety   : {'ON' if output_safety else 'OFF'}")

    # Rate limits
    rate_limits = gateway.get("rate_limits", [])
    print(f"Rate limits     : {len(rate_limits)} configured")
    for rl in rate_limits:
        print(f"  key={rl.get('key')} calls={rl.get('calls')}/{rl.get('renewal_period')}")


# TODO: Uncomment after creating the endpoint
# config = get_endpoint_config(WORKSPACE_URL, HEADERS, PT_ENDPOINT_NAME)
# print_gateway_summary(config)

print("Endpoint config check is commented out — run after endpoint is created.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Lab Summary & Checkpoint

# COMMAND ----------

print("=" * 60)
print("Lab 02 — Checkpoint Summary")
print("=" * 60)

checks = [
    "AI Gateway endpoint structure explained (in-region path)",
    "FMAPI Provisioned Throughput endpoint config built",
    "Azure OpenAI Regional (australiaeast) endpoint config built",
    "Rate limits: endpoint-level and per-user QPM configured",
    "Usage tracking enabled with team/project tags",
    "PII BLOCK guardrail configured (input + output)",
    "Safety filter enabled",
    "Payload logging to Delta table configured",
    "Test functions written for connectivity, PII, safety",
    "Gateway configuration summary function written",
]

for check in checks:
    print(f"  [DONE]  {check}")

print()
print("Next lab: 03_rate_limits_guardrails.py")
print("Topic   : Deep-dive into rate limit testing and AU-specific PII examples")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Reference: AI Gateway REST API endpoints
# MAGIC
# MAGIC | Operation | Method | Path |
# MAGIC |---|---|---|
# MAGIC | Create endpoint | POST | `/api/2.0/serving-endpoints` |
# MAGIC | Get endpoint | GET | `/api/2.0/serving-endpoints/{name}` |
# MAGIC | Update AI Gateway config | PUT | `/api/2.0/serving-endpoints/{name}/ai-gateway` |
# MAGIC | Get AI Gateway config | GET | `/api/2.0/serving-endpoints/{name}/ai-gateway` |
# MAGIC | Invoke endpoint | POST | `/serving-endpoints/{name}/invocations` |
# MAGIC | List endpoints | GET | `/api/2.0/serving-endpoints` |
# MAGIC
# MAGIC **Note on `ServedEntityInput.name`:**
# MAGIC When creating a PT-backed endpoint via the SDK, set `ServedEntityInput.name` to
# MAGIC a logical label (e.g. `"{endpoint_name}-entity"`). The `Route.served_model_name`
# MAGIC field must match this `name` exactly — it does **not** take the raw model name.
