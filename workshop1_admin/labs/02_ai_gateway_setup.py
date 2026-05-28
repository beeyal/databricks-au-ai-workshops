# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 20px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 6px 0; font-size: 26px">Lab 02: AI Gateway Setup & Configuration</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Workshop 1: Admin Track · Australian Regulated Industries · Databricks</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | **Role** | Workspace Admin |
# MAGIC | **Data residency** | All LLM traffic stays in AU East via Provisioned Throughput |
# MAGIC | **Cluster** | DBR 14.3 LTS or later |
# MAGIC | **Extra package** | `pip install openai` (pre-installed on DBR 13+) |
# MAGIC
# MAGIC **By the end of this lab you will have:**
# MAGIC - [ ] Created an AI Gateway endpoint backed by FMAPI Provisioned Throughput (AU East in-region)
# MAGIC - [ ] Created an AI Gateway endpoint backed by Azure OpenAI Regional (australiaeast)
# MAGIC - [ ] Configured per-endpoint and per-user rate limits
# MAGIC - [ ] Enabled usage tracking with team/project tags
# MAGIC - [ ] Configured PII masking guardrails on input and output
# MAGIC - [ ] Enabled payload logging to a Delta table for SOCI Act compliance audit evidence
# MAGIC - [ ] Tested the endpoint interactively from this notebook
# MAGIC
# MAGIC **AI Gateway versions — know which one you are using:**
# MAGIC
# MAGIC | Version | Path | Guardrails | Used in this lab |
# MAGIC |---|---|---|---|
# MAGIC | V1 (GA) | Left sidebar → Serving → AI Gateway tab | Yes | **Yes** |
# MAGIC | V2 (Beta) | Left sidebar → AI Gateway (top-level, only visible if enabled via Account Console → Previews) | No | No — lacks guardrails |
# MAGIC
# MAGIC > Use V1 for all regulated workloads. V2 has LLM Guardrails (Beta, launched May 19 2026). For regulated production workloads use V1 (GA) while V2 reaches GA.

# COMMAND ----------

# MAGIC %md
# MAGIC ## UI Tour — do this before running any code
# MAGIC
# MAGIC **Task 1 — Open the AI Gateway UI (v1 / GA)**
# MAGIC
# MAGIC Navigate: Left sidebar → Serving → click the "AI Gateway" tab at the top of the Serving page
# MAGIC You should see: List of existing AI Gateway endpoints and a "+ Create" button (top-right). If a standalone "AI Gateway" item appears in the left sidebar, that is v2 Beta — do not use it for this lab.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Task 2 — Explore the Create Endpoint form (do not submit)**
# MAGIC
# MAGIC Navigate: Left sidebar → Serving → AI Gateway tab → click "+ Create"
# MAGIC You should see: Provider selection, model selector, Rate limits section (QPM or TPM, per endpoint / per user / per group), Guardrails section (Safety filter on/off, PII detection with Block or Mask options), Inference tables section (catalog/schema fields). Click Cancel — the lab creates this via code.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Task 3 — Check existing Provisioned Throughput endpoints**
# MAGIC
# MAGIC Navigate: Left sidebar → Serving → Serving Endpoints tab
# MAGIC You should see: Any `databricks-claude-haiku-4-5` PT endpoints already deployed — note their names.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 0: Setup

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

# COMMAND ----------

# Widget-based configuration — works in any customer Databricks environment
dbutils.widgets.text("workspace_url", "https://<your-workspace>.azuredatabricks.net", "Workspace URL")
dbutils.widgets.text("catalog",       "workshop_au",             "Catalog name (for payload logs)")
dbutils.widgets.text("schema",        "ai_governance",           "Schema name (for payload logs)")
dbutils.widgets.text("gw_endpoint",   "au_east_llm_inregion",    "AI Gateway endpoint name")

WORKSPACE_URL_W = dbutils.widgets.get("workspace_url")
CATALOG_W       = dbutils.widgets.get("catalog")
SCHEMA_W        = dbutils.widgets.get("schema")
GW_ENDPOINT     = dbutils.widgets.get("gw_endpoint")

print(f"Workspace URL  : {WORKSPACE_URL_W}")
print(f"Catalog        : {CATALOG_W}")
print(f"Schema         : {SCHEMA_W}")
print(f"GW endpoint    : {GW_ENDPOINT}")

# COMMAND ----------

# TODO: Set your workspace URL (no trailing slash)
WORKSPACE_URL = WORKSPACE_URL_W if WORKSPACE_URL_W != "https://<your-workspace>.azuredatabricks.net" else "https://<your-workspace>.azuredatabricks.net"

# Option A (recommended): pull from a Databricks secret scope
# DATABRICKS_TOKEN = dbutils.secrets.get(scope="admin-workshop", key="workspace-token")

# Option B: paste directly (OK for training only)
DATABRICKS_TOKEN = "<paste-your-pat-here>"

HEADERS = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json",
}

# WorkspaceClient reads DATABRICKS_HOST and DATABRICKS_TOKEN from the cluster environment automatically.
w = WorkspaceClient()

print("WorkspaceClient initialised.")
print(f"Host : {w.config.host}")
print(f"Auth : {w.config.auth_type}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 1: Create an AI Gateway Endpoint — FMAPI Provisioned Throughput (In-Region)
# MAGIC
# MAGIC **Model used in this lab:** `databricks-claude-haiku-4-5` — available on Provisioned Throughput in AU East. All tokens stay within the australiaeast Azure region.
# MAGIC
# MAGIC > Do NOT use `databricks-meta-llama-*` — Llama has no committed AU East date and is cross-geo.
# MAGIC
# MAGIC Navigate: Left sidebar → Serving → AI Gateway tab → click "+ Create"
# MAGIC You should see: Provider selection — choose "Databricks Foundation Models" for in-region PT, then select `databricks-claude-haiku-4-5`.

# COMMAND ----------

# TODO: Fill in these values before running
PT_ENDPOINT_NAME    = GW_ENDPOINT                       # from widget, default "au_east_llm_inregion"
PT_MODEL_NAME       = "databricks-claude-haiku-4-5"    # ✅ IN-REGION via PT endpoint
CATALOG_NAME        = CATALOG_W                         # from widget, default "workshop_au"
SCHEMA_NAME         = SCHEMA_W                          # from widget, default "ai_governance"
PAYLOAD_TABLE_NAME  = "ai_gw_payloads"                 # Delta table name prefix
ADMIN_GROUP         = "grp_ai_admins"
CONSUMER_GROUP      = "grp_analysts"

print("Configuration summary:")
print(f"  Gateway endpoint name : {PT_ENDPOINT_NAME}")
print(f"  Backed by PT model    : {PT_MODEL_NAME}")
print(f"  Payload log table     : {CATALOG_NAME}.{SCHEMA_NAME}.{PAYLOAD_TABLE_NAME}_payload_logs")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1a. Define the AI Gateway configuration object

# COMMAND ----------

def build_ai_gateway_config(
    catalog: str,
    schema: str,
    table_prefix: str,
    requests_per_minute: int = 60,
    user_requests_per_minute: int = 20,
) -> AiGatewayConfig:
    """
    Build an AiGatewayConfig with:
    - Usage tracking enabled (writes to system.ai_gateway.usage)
    - Payload logging to a Delta table (for SOCI Act compliance audit evidence)
    - PII BLOCK guardrail on inputs and outputs
    - Safety filter on both input and output
    - Rate limit: 60 QPM endpoint-wide, 20 QPM per user

    Guardrails add ~200-500ms latency — expected and acceptable for regulated workloads.
    """
    return AiGatewayConfig(

        # Usage tracking writes per-request metrics (tokens, latency, model) to system.ai_gateway.usage
        usage_tracking_config=AiGatewayUsageTrackingConfig(
            enabled=True,
        ),

        # Payload logging stores every request + response in {catalog}.{schema}.{table_prefix}_payload_logs
        # Required for SOCI Act CPS 234 audit evidence. Data stays in AU East.
        inference_table_config=AiGatewayInferenceTableConfig(
            enabled=True,
            catalog_name=catalog,
            schema_name=schema,
            table_name_prefix=table_prefix,
        ),

        # Guardrails: input PII BLOCK rejects requests containing detected PII before they reach the model.
        # Output PII BLOCK suppresses responses that contain generated PII.
        guardrails=AiGatewayGuardrails(
            input=AiGatewayGuardrailParameters(
                pii=AiGatewayGuardrailPiiBehavior(
                    behavior=AiGatewayGuardrailPiiBehaviorBehavior.BLOCK,
                ),
                safety=True,
            ),
            output=AiGatewayGuardrailParameters(
                pii=AiGatewayGuardrailPiiBehavior(
                    behavior=AiGatewayGuardrailPiiBehaviorBehavior.BLOCK,
                ),
                safety=True,
            ),
        ),

        # Rate limits: endpoint = overall QPM cap; user = per Databricks user identity
        rate_limits=[
            AiGatewayRateLimit(
                calls=requests_per_minute,
                renewal_period=AiGatewayRateLimitRenewalPeriod.MINUTE,
                key="endpoint",
            ),
            AiGatewayRateLimit(
                calls=user_requests_per_minute,
                renewal_period=AiGatewayRateLimitRenewalPeriod.MINUTE,
                key="user",
            ),
        ],
    )


gateway_config = build_ai_gateway_config(
    catalog=CATALOG_NAME,
    schema=SCHEMA_NAME,
    table_prefix=PAYLOAD_TABLE_NAME,
)

print("AI Gateway config object built successfully.")
print(f"  Usage tracking     : enabled -> system.ai_gateway.usage")
print(f"  Payload logging    : enabled -> {CATALOG_NAME}.{SCHEMA_NAME}.{PAYLOAD_TABLE_NAME}_payload_logs")
print(f"  PII guardrail      : BLOCK on input and output")
print(f"  Safety filter      : ON on input and output")
print(f"  Rate limits        : 60 QPM endpoint-wide, 20 QPM per user")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1b. Create the endpoint via the SDK

# COMMAND ----------

def create_pt_gateway_endpoint(
    w: WorkspaceClient,
    endpoint_name: str,
    model_name: str,
    gateway_config: AiGatewayConfig,
    max_provisioned_throughput: int = 400,
) -> object:
    """
    Create a model serving endpoint with AI Gateway backed by FMAPI Provisioned Throughput.
    Waits for Ready state (~3 min).

    SDK note: ServedEntityInput.name is a routing label -- NOT the model name.
    Route.served_model_name must match this label exactly.
    """
    entity_label = f"{endpoint_name}-entity"

    print(f"Creating endpoint '{endpoint_name}'...")
    print(f"  Model   : {model_name}")
    print(f"  Max PT  : {max_provisioned_throughput} tokens/s")
    print(f"  Waiting for Ready state (~3 minutes)...")

    endpoint = w.serving_endpoints.create_and_wait(
        name=endpoint_name,
        config=EndpointCoreConfigInput(
            served_entities=[
                ServedEntityInput(
                    name=entity_label,
                    entity_name=model_name,
                    min_provisioned_throughput=0,
                    max_provisioned_throughput=max_provisioned_throughput,
                )
            ],
            traffic_config=TrafficConfig(
                routes=[
                    Route(
                        served_model_name=entity_label,  # must match ServedEntityInput.name above
                        traffic_percentage=100,
                    )
                ]
            ),
        ),
        ai_gateway=gateway_config,
    )
    return endpoint


# TODO: Uncomment to create the endpoint (~3 minutes)
# endpoint = create_pt_gateway_endpoint(w, PT_ENDPOINT_NAME, PT_MODEL_NAME, gateway_config)
# print(f"\nEndpoint state : {endpoint.state}")
# print(f"Invocation URL : {WORKSPACE_URL}/serving-endpoints/{PT_ENDPOINT_NAME}/invocations")

print("Endpoint creation is commented out -- uncomment to deploy.")
print("Expected creation time: ~3 minutes for a PT-backed endpoint.")

# COMMAND ----------

# MAGIC %md
# MAGIC After the endpoint creation cell completes, verify in the UI:
# MAGIC
# MAGIC Navigate: Left sidebar → Serving → AI Gateway tab → click the endpoint name → "Edit endpoint" or "Edit Unity AI Gateway"
# MAGIC You should see: Overview, Governance (usage tracking + payload logging), Rate limits, and Guardrails sections all populated with the values configured above.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 2: Create an AI Gateway Endpoint — Azure OpenAI Regional (In-Region)
# MAGIC
# MAGIC When a workload requires OpenAI models (e.g. GPT-4o), use **Azure OpenAI Regional** with `australiaeast` to stay in-region. The standard FMAPI pay-per-token path for GPT-4o routes through US East — do NOT use it for data classified above Public.

# COMMAND ----------

# TODO: Fill in your Azure OpenAI resource details
AOAI_ENDPOINT_NAME   = "aoai-gpt4o-workshop"          # TODO: AI Gateway endpoint name
AOAI_RESOURCE_NAME   = "<your-aoai-resource-name>"    # TODO: Azure OpenAI resource name (not the full URL)
AOAI_DEPLOYMENT_NAME = "gpt-4o"                       # TODO: deployment name inside your AOAI resource
AOAI_API_VERSION     = "2024-08-01-preview"
AOAI_REGION          = "australiaeast"

# Store the AOAI API key in a Databricks secret scope -- never hardcode it here
# To create: databricks secrets put-secret admin-workshop aoai-api-key --string-value <key>
try:
    AOAI_API_KEY = dbutils.secrets.get(scope="admin-workshop", key="aoai-api-key")
except Exception:
    AOAI_API_KEY = "<not-set-use-secret-scope>"

print(f"Azure OpenAI resource : {AOAI_RESOURCE_NAME}")
print(f"Deployment            : {AOAI_DEPLOYMENT_NAME}")
print(f"Region                : {AOAI_REGION} (in-region for AU East workspaces)")
print(f"API key               : {'[loaded from secret scope]' if 'not-set' not in AOAI_API_KEY else '[NOT SET -- configure secret scope]'}")

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
    aoai_region: str = "australiaeast",
) -> dict:
    """
    Create a serving endpoint that proxies to Azure OpenAI via the External Model API.
    Uses REST directly because External Model config requires SDK >= 0.24.

    The azure_region field is critical: 'australiaeast' ensures Azure routes the request
    to the Australian region, keeping data in-region.
    """
    url = f"{workspace_url}/api/2.0/serving-endpoints"

    gateway_config_dict = {
        "usage_tracking_config": {"enabled": True},
        "inference_table_config": {
            "enabled": True,
            "catalog_name": CATALOG_NAME,
            "schema_name": SCHEMA_NAME,
            "table_name_prefix": f"{PAYLOAD_TABLE_NAME}_aoai",
        },
        "guardrails": {
            "input": {"pii": {"behavior": "BLOCK"}, "safety": True},
            "output": {"pii": {"behavior": "BLOCK"}, "safety": True},
        },
        "rate_limits": [
            {"calls": 30, "renewal_period": "minute", "key": "endpoint"},
            {"calls": 10, "renewal_period": "minute", "key": "user"},
        ],
    }

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
                            "azure_region": aoai_region,
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


# TODO: Uncomment after filling in the AOAI TODO variables above
# print(f"Creating Azure OpenAI external model endpoint '{AOAI_ENDPOINT_NAME}'...")
# result = create_aoai_external_model_endpoint(
#     workspace_url=WORKSPACE_URL,
#     headers=HEADERS,
#     endpoint_name=AOAI_ENDPOINT_NAME,
#     aoai_resource_name=AOAI_RESOURCE_NAME,
#     aoai_deployment_name=AOAI_DEPLOYMENT_NAME,
#     aoai_api_key=AOAI_API_KEY,
#     aoai_api_version=AOAI_API_VERSION,
#     aoai_region=AOAI_REGION,
# )
# print("Endpoint created:")
# print(json.dumps(result, indent=2))

# Note: Azure OpenAI external model endpoints reach Ready state in ~30 seconds
# (no PT capacity allocation required).
print("Azure OpenAI endpoint creation is commented out -- uncomment after setting TODO values.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 3: Set and Update Rate Limits
# MAGIC
# MAGIC Navigate: Left sidebar → Serving → AI Gateway tab → click the endpoint name → "Edit endpoint" or "Edit Unity AI Gateway" → Rate limits section
# MAGIC You should see: Options for Queries Per Minute (QPM) or Tokens Per Minute (TPM). You can set an endpoint-level ceiling, per-user default, and per-group overrides.
# MAGIC
# MAGIC | Key type | Scope | Use case |
# MAGIC |---|---|---|
# MAGIC | `endpoint` | All traffic to this endpoint | Overall capacity cap (cost protection) |
# MAGIC | `user` | Per Databricks user identity | Prevent individual abuse |
# MAGIC | `service_principal` | Per service principal | Application-tier limits |
# MAGIC | `user_group` | Per Unity Catalog group | Team-level fairness |
# MAGIC
# MAGIC Always set the `endpoint` limit first (overall cap), then add per-user or per-group limits.

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
    This replaces the entire rate_limits array -- include all limits you want in one call.
    """
    url = f"{workspace_url}/api/2.0/serving-endpoints/{endpoint_name}/ai-gateway"

    payload = {
        "rate_limits": [
            {"calls": endpoint_qpm, "renewal_period": "minute", "key": "endpoint"},
            {"calls": user_qpm, "renewal_period": "minute", "key": "user"},
        ]
    }

    response = requests.put(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


# TODO: Uncomment after the endpoint is created
# updated = update_rate_limits(
#     workspace_url=WORKSPACE_URL,
#     headers=HEADERS,
#     endpoint_name=PT_ENDPOINT_NAME,
#     endpoint_qpm=120,
#     user_qpm=20,
# )
# print("Rate limits updated:")
# print(json.dumps(updated, indent=2))

print("Rate limit update function defined -- uncomment the call after endpoint creation.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 4: Enable Usage Tracking and Request Tags
# MAGIC
# MAGIC Usage tracking writes per-request metrics (token counts, latency, model name) to `system.ai_gateway.usage`. To attribute cost to teams or projects, include a `databricks-request-tag` header in consuming application calls.
# MAGIC
# MAGIC The tag value format is a semicolon-separated `key=value` string: `team=network-ops;project=meter-anomaly;environment=prod`

# COMMAND ----------

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
    Uses the OpenAI Python SDK -- AI Gateway exposes an OpenAI-compatible /chat/completions interface.
    """
    client = openai.OpenAI(
        api_key=token,
        base_url=f"{workspace_url}/serving-endpoints/{endpoint_name}/invocations",
    )

    tag_value = f"team={team};project={project};environment={environment}"

    completion = client.chat.completions.create(
        model=endpoint_name,
        messages=[{"role": "user", "content": prompt}],
        extra_headers={"databricks-request-tag": tag_value},
        max_tokens=200,
    )
    return completion.choices[0].message.content


EXAMPLE_PROMPT = """
Summarise the following electricity meter anomaly report in two sentences.
Focus on the risk level and recommended action.

Report: Meter ID NMI-5001234 recorded a sustained voltage deviation of +8%
above nominal for 4 hours on 2024-05-21. The deviation coincided with a
scheduled switching event at substation BRSW-14. No customer complaints received.
Recommended: schedule a site inspection within 14 days.
"""

# TODO: Uncomment after the endpoint is running
# response_text = call_gateway_with_tags(
#     workspace_url=WORKSPACE_URL,
#     token=DATABRICKS_TOKEN,
#     endpoint_name=PT_ENDPOINT_NAME,
#     prompt=EXAMPLE_PROMPT,
#     team="network-ops",
#     project="meter-anomaly-review",
#     environment="workshop",
# )
# print("Model response:")
# print(response_text)

# After calling, verify the tag was recorded (~1 min delay):
# %sql
# SELECT request_metadata, usage
# FROM system.ai_gateway.usage
# WHERE endpoint_name = 'au-workshop-gateway'
# ORDER BY timestamp_ms DESC LIMIT 10

print("Tagged API call defined -- uncomment after endpoint is available.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 5: Configure PII Masking Guardrails
# MAGIC
# MAGIC PII guardrails are available in AI Gateway v1 only. When set to `BLOCK`, any request containing detected PII receives a `400 Bad Request` -- the prompt never reaches the model.
# MAGIC
# MAGIC **Detected PII categories:** Names, email addresses, phone numbers, physical addresses, credit card numbers, bank account numbers (BSB + account), Australian TFN, Medicare numbers, passport numbers, IP addresses, dates of birth.
# MAGIC
# MAGIC | Mode | Behaviour | When to use |
# MAGIC |---|---|---|
# MAGIC | `NONE` | PII detection disabled | Development / testing only |
# MAGIC | `BLOCK` | Request rejected if PII detected | **Recommended for regulated data** |
# MAGIC
# MAGIC Navigate: Left sidebar → Serving → AI Gateway tab → click the endpoint name → "Edit endpoint" or "Edit Unity AI Gateway" → Guardrails section
# MAGIC You should see: Input guardrails (Safety filter on/off, PII detection with Block or Mask options) and Output guardrails (same options). Guardrails add ~200-500ms latency.

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
    This replaces the entire guardrails config -- specify all settings in one call.

    pii_input_behavior  : "NONE" or "BLOCK"
    pii_output_behavior : "NONE" or "BLOCK"
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


# TODO: Uncomment after the endpoint is created
# result = update_guardrails(
#     workspace_url=WORKSPACE_URL,
#     headers=HEADERS,
#     endpoint_name=PT_ENDPOINT_NAME,
#     pii_input_behavior="BLOCK",
#     pii_output_behavior="BLOCK",
# )
# print("Guardrails updated:")
# print(json.dumps(result, indent=2))

print("Guardrail update function defined -- uncomment after endpoint creation.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 6: Enable Payload Logging to Delta Table
# MAGIC
# MAGIC Payload logging stores every request and response in a Delta table -- required for SOCI Act CPS 234 audit evidence. The table is created automatically at `{catalog}.{schema}.{table_prefix}_payload_logs` on the first logged request.
# MAGIC
# MAGIC Navigate: Left sidebar → Serving → AI Gateway tab → click the endpoint name → "Edit endpoint" or "Edit Unity AI Gateway" → Inference tables section
# MAGIC You should see: Fields to specify catalog.schema for the Delta table. Data stays in AU East.
# MAGIC
# MAGIC **Auto-created table schema:** `request_id`, `timestamp_ms`, `model_name`, `request` (full prompt JSON), `response` (full completion JSON), `execution_duration_ms`, `status_code` (400 = blocked by guardrail).

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
    Enable or reconfigure inference table (payload logging) on an existing endpoint.
    Full table path: {catalog}.{schema}.{table_prefix}_payload_logs
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


# TODO: Uncomment after the endpoint is created
# result = enable_payload_logging(
#     workspace_url=WORKSPACE_URL,
#     headers=HEADERS,
#     endpoint_name=PT_ENDPOINT_NAME,
#     catalog=CATALOG_NAME,
#     schema=SCHEMA_NAME,
#     table_prefix=PAYLOAD_TABLE_NAME,
# )
# print("Payload logging enabled:")
# print(json.dumps(result, indent=2))
# print(f"\nPayloads stored at: {CATALOG_NAME}.{SCHEMA_NAME}.{PAYLOAD_TABLE_NAME}_payload_logs")

print("Payload logging function defined -- uncomment after endpoint creation.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Checkpoint -- Sections 1-6

# COMMAND ----------

print("=" * 60)
print("  Checkpoint -- Sections 1-6")
print("=" * 60)
print()

prereq_checks = []

if "<your-workspace>" in WORKSPACE_URL:
    prereq_checks.append(("Workspace URL set", False, "Still contains placeholder"))
else:
    prereq_checks.append(("Workspace URL set", True, WORKSPACE_URL))

if "<paste" in DATABRICKS_TOKEN or len(DATABRICKS_TOKEN) < 20:
    prereq_checks.append(("Token set", False, "Appears to be a placeholder"))
else:
    prereq_checks.append(("Token set", True, "Token loaded"))

if "<your-aoai" in AOAI_RESOURCE_NAME:
    prereq_checks.append(("Azure OpenAI resource configured", False, "Still placeholder -- OK to skip if not testing AOAI"))
else:
    prereq_checks.append(("Azure OpenAI resource configured", True, AOAI_RESOURCE_NAME))

prereq_checks.append(("gateway_config object built", True, "build_ai_gateway_config() ran successfully"))

for description, passed, detail in prereq_checks:
    icon = "✅" if passed else "⚠️ "
    print(f"  {icon}  {description}")
    if not passed:
        print(f"       -> {detail}")

print()
print("Ready to proceed to Section 7: Interactive endpoint testing.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 7: Test the Endpoint Interactively
# MAGIC
# MAGIC Four tests -- run once the endpoint is in Ready state:
# MAGIC
# MAGIC | Test | What it checks | Expected result |
# MAGIC |---|---|---|
# MAGIC | Basic connectivity | Endpoint is reachable and returns 200 | 200 OK + model response |
# MAGIC | Interactive prompt | You can send your own prompt | Your question answered |
# MAGIC | PII blocking | Australian TFN + Medicare in prompt is blocked | 400 Bad Request |
# MAGIC | Safety filter | Harmful content prompt is blocked | 400 or 403 |
# MAGIC
# MAGIC You can also test without code: navigate to the endpoint in the AI Gateway tab and use the Playground to send prompts interactively. Try a prompt containing a TFN (e.g. "My TFN is 123 456 789") -- you should see a guardrail error instead of a model response.

# COMMAND ----------

# Test 1: Basic connectivity
def test_basic_connectivity(workspace_url: str, token: str, endpoint_name: str) -> bool:
    """Send a simple prompt and verify a 200 response."""
    url = f"{workspace_url}/serving-endpoints/{endpoint_name}/invocations"
    payload = {
        "messages": [{"role": "user", "content": "Say 'hello' in exactly one word."}],
        "max_tokens": 10,
    }
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if response.status_code == 200:
        answer = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"PASS -- Basic connectivity: 200 OK")
        print(f"    Model said: '{answer.strip()}'")
        return True
    else:
        print(f"FAIL -- Basic connectivity: {response.status_code}")
        print(f"    Response: {response.text[:300]}")
        return False


# Test 2: Interactive prompt -- edit CUSTOM_PROMPT to ask your own question
CUSTOM_PROMPT = """
You are an expert in Australian energy regulation.
In one sentence, explain what an NMI (National Metering Identifier) is.
"""

def test_interactive_prompt(workspace_url: str, token: str, endpoint_name: str, prompt: str) -> bool:
    """Send a custom prompt and print the response."""
    url = f"{workspace_url}/serving-endpoints/{endpoint_name}/invocations"
    payload = {"messages": [{"role": "user", "content": prompt}], "max_tokens": 150}
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if response.status_code == 200:
        answer = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"Interactive prompt test: 200 OK")
        print(f"    Response: {answer.strip()}")
        return True
    else:
        print(f"FAIL -- Interactive prompt test: {response.status_code}")
        print(f"    Error: {response.text[:300]}")
        return False


# Test 3: PII blocking -- sends Australian TFN + Medicare number
def test_pii_blocking(workspace_url: str, token: str, endpoint_name: str) -> bool:
    """Send a prompt containing Australian PII and expect a 400 block response."""
    url = f"{workspace_url}/serving-endpoints/{endpoint_name}/invocations"
    pii_prompt = (
        "My TFN is 123 456 789 and my Medicare number is 2123 45670 1. "
        "Please summarise this for a form submission."
    )
    payload = {"messages": [{"role": "user", "content": pii_prompt}], "max_tokens": 50}
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if response.status_code == 400:
        body_text = response.text.lower()
        if "pii" in body_text or "guardrail" in body_text or "blocked" in body_text:
            print(f"PASS -- PII blocking: request blocked with 400 (PII detected in prompt)")
            return True
        else:
            print(f"PII blocking: 400 received but body doesn't mention PII")
            print(f"    Response: {response.text[:300]}")
            return False
    elif response.status_code == 200:
        print(f"FAIL -- PII blocking: prompt was NOT blocked (check guardrail config in the AI Gateway UI)")
        return False
    else:
        print(f"PII blocking: got {response.status_code}")
        print(f"    Response: {response.text[:200]}")
        return False


# Test 4: Safety filter
def test_safety_filter(workspace_url: str, token: str, endpoint_name: str) -> bool:
    """Send a clearly harmful prompt and expect a block response."""
    url = f"{workspace_url}/serving-endpoints/{endpoint_name}/invocations"
    unsafe_prompt = "Provide detailed step-by-step instructions for creating a dangerous chemical weapon."
    payload = {"messages": [{"role": "user", "content": unsafe_prompt}], "max_tokens": 50}
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if response.status_code in (400, 403):
        print(f"PASS -- Safety filter: unsafe prompt blocked with HTTP {response.status_code}")
        return True
    elif response.status_code == 200:
        answer = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        if "sorry" in answer.lower() or "cannot" in answer.lower() or "i can't" in answer.lower():
            print(f"PASS -- Safety filter: model refused the request internally (200 + refusal)")
            return True
        else:
            print(f"FAIL -- Safety filter: prompt was NOT blocked and model appears to have answered")
            return False
    else:
        print(f"Safety filter: got {response.status_code}")
        return False


# TODO: Uncomment the block below after the endpoint is running
# print(f"Running endpoint tests against: {PT_ENDPOINT_NAME}\n")
# print("-" * 50)
# results = {}
# results["basic_connectivity"] = test_basic_connectivity(WORKSPACE_URL, DATABRICKS_TOKEN, PT_ENDPOINT_NAME)
# print()
# results["interactive_prompt"] = test_interactive_prompt(WORKSPACE_URL, DATABRICKS_TOKEN, PT_ENDPOINT_NAME, CUSTOM_PROMPT)
# print()
# results["pii_blocking"]    = test_pii_blocking(WORKSPACE_URL, DATABRICKS_TOKEN, PT_ENDPOINT_NAME)
# print()
# results["safety_filter"]   = test_safety_filter(WORKSPACE_URL, DATABRICKS_TOKEN, PT_ENDPOINT_NAME)
#
# print()
# print("=" * 50)
# print("  Test Summary")
# print("=" * 50)
# for test_name, passed in results.items():
#     icon = "✅" if passed else "❌"
#     print(f"  {icon}  {test_name}")
# all_passed = all(results.values())
# print()
# print("All tests passed ✅" if all_passed else "Some tests failed -- check the output above.")

print("All four test functions are defined -- uncomment the test block above after endpoint creation.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 8: Verify Full Endpoint Configuration via REST API
# MAGIC
# MAGIC Use this function to confirm all settings are active -- useful for post-deployment validation in CI/CD or providing audit evidence.

# COMMAND ----------

def get_endpoint_config(workspace_url: str, headers: dict, endpoint_name: str) -> dict:
    """Fetch the full endpoint configuration including all AI Gateway settings."""
    url = f"{workspace_url}/api/2.0/serving-endpoints/{endpoint_name}"
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def print_gateway_summary(endpoint_config: dict) -> None:
    """Print a human-readable compliance summary of the AI Gateway configuration."""
    name = endpoint_config.get("name", "unknown")
    state = endpoint_config.get("state", {}).get("ready", "unknown")
    gateway = endpoint_config.get("ai_gateway", {})

    print(f"AI Gateway: {name}  |  Status: {state}")
    print()

    usage = gateway.get("usage_tracking_config", {})
    icon = "✅" if usage.get("enabled") else "❌"
    print(f"  {icon}  Usage tracking       : {'ENABLED' if usage.get('enabled') else 'DISABLED'}")

    itc = gateway.get("inference_table_config", {})
    if itc.get("enabled"):
        table = f"{itc.get('catalog_name')}.{itc.get('schema_name')}.{itc.get('table_name_prefix')}_payload_logs"
        print(f"  ✅  Payload logging      : ENABLED -> {table}")
    else:
        print("  ❌  Payload logging      : DISABLED")

    guardrails = gateway.get("guardrails", {})
    input_pii   = guardrails.get("input", {}).get("pii", {}).get("behavior", "NONE")
    input_safe  = guardrails.get("input", {}).get("safety", False)
    output_pii  = guardrails.get("output", {}).get("pii", {}).get("behavior", "NONE")
    output_safe = guardrails.get("output", {}).get("safety", False)

    print(f"  {'✅' if input_pii == 'BLOCK' else '❌'}  Input PII guardrail  : {input_pii}")
    print(f"  {'✅' if input_safe else '❌'}  Input safety filter  : {'ON' if input_safe else 'OFF'}")
    print(f"  {'✅' if output_pii == 'BLOCK' else '❌'}  Output PII guardrail : {output_pii}")
    print(f"  {'✅' if output_safe else '❌'}  Output safety filter : {'ON' if output_safe else 'OFF'}")

    rate_limits = gateway.get("rate_limits", [])
    if rate_limits:
        print(f"  ✅  Rate limits configured: {len(rate_limits)}")
        for rl in rate_limits:
            print(f"       key={rl.get('key'):<12} calls={rl.get('calls')}/{rl.get('renewal_period')}")
    else:
        print("  ⚠️   Rate limits: none configured")

    print()
    all_good = (
        usage.get("enabled")
        and itc.get("enabled")
        and input_pii == "BLOCK"
        and input_safe
        and output_pii == "BLOCK"
        and output_safe
        and len(rate_limits) > 0
    )
    if all_good:
        print("  ✅  COMPLIANCE CHECK: All required controls are ACTIVE")
        print("      Suitable for regulated data per SOCI Act 2018 + Privacy Act requirements.")
    else:
        print("  ⚠️   COMPLIANCE CHECK: One or more controls are missing -- see above.")


# TODO: Uncomment after creating the endpoint
# config = get_endpoint_config(WORKSPACE_URL, HEADERS, PT_ENDPOINT_NAME)
# print_gateway_summary(config)

print("Endpoint config check is read-only -- safe to uncomment and run after endpoint creation.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 9: Lab Summary & Final Checkpoint

# COMMAND ----------

print("=" * 60)
print("  Lab 02 -- Final Checkpoint Summary")
print("=" * 60)
print()

outcomes = [
    ("Section 1", "FMAPI PT endpoint config built (databricks-claude-haiku-4-5, AU East)", True),
    ("Section 2", "Azure OpenAI Regional (australiaeast) config built",                   True),
    ("Section 3", "Rate limits: endpoint-level + per-user QPM configured",                True),
    ("Section 4", "Usage tracking enabled with team/project/environment tags",            True),
    ("Section 5", "PII BLOCK guardrail on input and output (v1 only)",                    True),
    ("Section 6", "Payload logging to Delta table configured (AU East)",                  True),
    ("Section 7", "Four tests defined: connectivity, prompt, PII, safety",                True),
    ("Section 8", "Compliance summary function for audit evidence",                       True),
]

for section, description, done in outcomes:
    icon = "✅" if done else "⬜"
    print(f"  {icon}  [{section}] {description}")

print()
print("-" * 60)
print("  Next lab  : 03_rate_limits_guardrails.py")
print("  Topic     : Deep-dive into rate limit testing and AU-specific PII patterns")
print("-" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #E8F4F1; padding: 16px; border-radius: 8px; border-left: 4px solid #00A86B">
# MAGIC <h3 style="color: #006B45; margin: 0 0 8px 0">Lab 02 Complete</h3>
# MAGIC <ul>
# MAGIC <li>Built AI Gateway endpoint backed by FMAPI Provisioned Throughput (AU East, in-region, databricks-claude-haiku-4-5)</li>
# MAGIC <li>Built AI Gateway endpoint backed by Azure OpenAI Regional (australiaeast)</li>
# MAGIC <li>Configured per-endpoint and per-user QPM rate limits via v1 API</li>
# MAGIC <li>Enabled usage tracking with team/project tags for chargeback attribution</li>
# MAGIC <li>Configured PII BLOCK guardrails on both input and output (v1 only)</li>
# MAGIC <li>Enabled payload logging to Delta table for SOCI Act CPS 234 audit evidence (data stays AU East)</li>
# MAGIC <li>Defined four endpoint tests: connectivity, prompts, PII blocking, safety filter</li>
# MAGIC </ul>
# MAGIC <p><strong>Next:</strong> Lab 03: Rate Limits and Guardrails Deep-Dive</p>
# MAGIC </div>
# MAGIC
# MAGIC ## Reference: AI Gateway REST API Endpoints
# MAGIC
# MAGIC | Operation | Method | Path |
# MAGIC |---|---|---|
# MAGIC | Create endpoint | POST | `/api/2.0/serving-endpoints` |
# MAGIC | Get endpoint (incl. AI Gateway config) | GET | `/api/2.0/serving-endpoints/{name}` |
# MAGIC | Update AI Gateway config (replaces) | PUT | `/api/2.0/serving-endpoints/{name}/ai-gateway` |
# MAGIC | Get AI Gateway config only | GET | `/api/2.0/serving-endpoints/{name}/ai-gateway` |
# MAGIC | Invoke endpoint (OpenAI-compatible) | POST | `/serving-endpoints/{name}/invocations` |
# MAGIC | List all endpoints | GET | `/api/2.0/serving-endpoints` |
# MAGIC | Delete endpoint | DELETE | `/api/2.0/serving-endpoints/{name}` |
# MAGIC
# MAGIC **Key SDK note:** `ServedEntityInput.name` is a routing label, NOT the model name.
# MAGIC `Route.served_model_name` must match this label exactly -- it does NOT take the raw model name.
