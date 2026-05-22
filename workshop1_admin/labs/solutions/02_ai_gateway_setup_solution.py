# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 02 SOLUTION: AI Gateway Setup & Configuration
# MAGIC
# MAGIC **This is the reference solution notebook. All TODO items are completed.**

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
import openai

# SOLUTION: Configuration — auto-populated from environment
WORKSPACE_URL   = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiUrl().getOrElse(None)
DATABRICKS_TOKEN = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().getOrElse(None)

HEADERS = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json",
}

# SOLUTION: Endpoint and catalog values
PT_ENDPOINT_NAME   = "pt-llama3-energy"
PT_MODEL_NAME      = "databricks-meta-llama-3-3-70b-instruct"
CATALOG_NAME       = "energy_ai"
SCHEMA_NAME        = "audit_logs"
PAYLOAD_TABLE_NAME = "ai_gateway_payloads"
AOAI_ENDPOINT_NAME   = "aoai-gpt4o-energy"
AOAI_RESOURCE_NAME   = dbutils.secrets.get(scope="admin-workshop", key="aoai-resource-name")
AOAI_DEPLOYMENT_NAME = "gpt-4o"
AOAI_API_VERSION     = "2024-08-01-preview"
AOAI_API_KEY         = dbutils.secrets.get(scope="admin-workshop", key="aoai-api-key")

ADMIN_GROUP    = "grp_ai_admins"
CONSUMER_GROUP = "grp_analysts"

w = WorkspaceClient()
print("WorkspaceClient initialised.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Build AI Gateway Config — SOLUTION

# COMMAND ----------

# SOLUTION: Build the AI Gateway config
def build_ai_gateway_config(
    catalog: str,
    schema: str,
    table: str,
    requests_per_minute: int = 60,
) -> AiGatewayConfig:
    return AiGatewayConfig(
        usage_tracking_config=AiGatewayUsageTrackingConfig(enabled=True),
        inference_table_config=AiGatewayInferenceTableConfig(
            enabled=True,
            catalog_name=catalog,
            schema_name=schema,
            table_name_prefix=table,
        ),
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
        rate_limits=[
            AiGatewayRateLimit(
                calls=requests_per_minute,
                renewal_period=AiGatewayRateLimitRenewalPeriod.MINUTE,
                key="endpoint",
            ),
            AiGatewayRateLimit(
                calls=20,
                renewal_period=AiGatewayRateLimitRenewalPeriod.MINUTE,
                key="user",
            ),
        ],
    )


gateway_config = build_ai_gateway_config(CATALOG_NAME, SCHEMA_NAME, PAYLOAD_TABLE_NAME)
print("AI Gateway config built: PII BLOCK, safety ON, usage tracking ON, payload logging ON.")
print("Rate limits: 60 QPM endpoint, 20 QPM per user.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Create FMAPI PT Endpoint — SOLUTION

# COMMAND ----------

# SOLUTION: Create the provisioned throughput AI Gateway endpoint
def create_pt_gateway_endpoint(
    w: WorkspaceClient,
    endpoint_name: str,
    model_name: str,
    gateway_config: AiGatewayConfig,
) -> object:
    return w.serving_endpoints.create_and_wait(
        name=endpoint_name,
        config=EndpointCoreConfigInput(
            served_entities=[
                ServedEntityInput(
                    entity_name=model_name,
                    min_provisioned_throughput=0,
                    max_provisioned_throughput=400,
                )
            ],
            traffic_config=TrafficConfig(
                routes=[Route(served_model_name=model_name, traffic_percentage=100)]
            ),
        ),
        ai_gateway=gateway_config,
    )


print(f"Creating PT endpoint '{PT_ENDPOINT_NAME}'...")
endpoint = create_pt_gateway_endpoint(w, PT_ENDPOINT_NAME, PT_MODEL_NAME, gateway_config)
print(f"Endpoint state : {endpoint.state}")
print(f"Endpoint URL   : {WORKSPACE_URL}/serving-endpoints/{PT_ENDPOINT_NAME}/invocations")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Create Azure OpenAI External Model Endpoint — SOLUTION

# COMMAND ----------

# SOLUTION: Create Azure OpenAI external model endpoint
def create_aoai_external_model_endpoint(
    workspace_url, headers, endpoint_name, aoai_resource_name,
    aoai_deployment_name, aoai_api_key, aoai_api_version, gateway_config_dict,
):
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


gateway_config_dict = {
    "usage_tracking_config": {"enabled": True},
    "inference_table_config": {
        "enabled": True,
        "catalog_name": CATALOG_NAME,
        "schema_name": SCHEMA_NAME,
        "table_name_prefix": f"{PAYLOAD_TABLE_NAME}_aoai",
    },
    "guardrails": {
        "input":  {"pii": {"behavior": "BLOCK"}, "safety": True},
        "output": {"pii": {"behavior": "BLOCK"}, "safety": True},
    },
    "rate_limits": [
        {"calls": 30, "renewal_period": "minute", "key": "endpoint"},
        {"calls": 10, "renewal_period": "minute", "key": "user"},
    ],
}

print(f"Creating Azure OpenAI external model endpoint '{AOAI_ENDPOINT_NAME}'...")
aoai_result = create_aoai_external_model_endpoint(
    workspace_url=WORKSPACE_URL, headers=HEADERS,
    endpoint_name=AOAI_ENDPOINT_NAME,
    aoai_resource_name=AOAI_RESOURCE_NAME,
    aoai_deployment_name=AOAI_DEPLOYMENT_NAME,
    aoai_api_key=AOAI_API_KEY,
    aoai_api_version=AOAI_API_VERSION,
    gateway_config_dict=gateway_config_dict,
)
print("Azure OpenAI endpoint created:")
print(json.dumps(aoai_result, indent=2))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Tagged API Call — SOLUTION

# COMMAND ----------

# SOLUTION: Call with usage tracking tags
def call_gateway_with_tags(workspace_url, token, endpoint_name, prompt, team, project, environment="dev"):
    client = openai.OpenAI(
        api_key=token,
        base_url=f"{workspace_url}/serving-endpoints/{endpoint_name}/invocations",
    )
    tag_value = f"team={team};project={project};environment={environment}"
    completion = client.chat.completions.create(
        model=endpoint_name,
        messages=[{"role": "user", "content": prompt}],
        extra_headers={"databricks-request-tag": tag_value},
    )
    return completion.choices[0].message.content


EXAMPLE_PROMPT = (
    "Summarise the following meter anomaly report in two sentences. "
    "Meter ID NMI-5001234 recorded +8% voltage deviation for 4 hours on 2024-05-21. "
    "Coincided with switching event at substation BRSW-14. No customer complaints. "
    "Recommend site inspection within 14 days."
)

response_text = call_gateway_with_tags(
    workspace_url=WORKSPACE_URL,
    token=DATABRICKS_TOKEN,
    endpoint_name=PT_ENDPOINT_NAME,
    prompt=EXAMPLE_PROMPT,
    team="network-ops",
    project="meter-anomaly-review",
    environment="prod",
)
print("Model response:")
print(response_text)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5–6. Guardrails & Payload Logging — SOLUTION

# COMMAND ----------

# SOLUTION: Update guardrails and payload logging on existing endpoint
def update_guardrails(workspace_url, headers, endpoint_name):
    url = f"{workspace_url}/api/2.0/serving-endpoints/{endpoint_name}/ai-gateway"
    payload = {
        "guardrails": {
            "input":  {"pii": {"behavior": "BLOCK"}, "safety": True},
            "output": {"pii": {"behavior": "BLOCK"}, "safety": True},
        },
        "inference_table_config": {
            "enabled": True,
            "catalog_name": CATALOG_NAME,
            "schema_name": SCHEMA_NAME,
            "table_name_prefix": PAYLOAD_TABLE_NAME,
        },
    }
    response = requests.put(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


result = update_guardrails(WORKSPACE_URL, HEADERS, PT_ENDPOINT_NAME)
print("Guardrails and payload logging updated:")
print(json.dumps(result, indent=2))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Endpoint Tests — SOLUTION

# COMMAND ----------

# SOLUTION: Run all endpoint tests
def test_basic_connectivity(workspace_url, token, endpoint_name):
    url = f"{workspace_url}/serving-endpoints/{endpoint_name}/invocations"
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"messages": [{"role": "user", "content": "Say hello."}], "max_tokens": 10},
        timeout=30,
    )
    passed = r.status_code == 200
    print(f"  {'[PASS]' if passed else '[FAIL]'} Basic connectivity: {r.status_code}")
    return passed


def test_pii_blocking(workspace_url, token, endpoint_name):
    url = f"{workspace_url}/serving-endpoints/{endpoint_name}/invocations"
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "messages": [{"role": "user", "content": "My TFN is 123 456 789."}],
            "max_tokens": 20,
        },
        timeout=30,
    )
    passed = r.status_code == 400
    print(f"  {'[PASS]' if passed else '[FAIL]'} PII blocking: {r.status_code}")
    return passed


def test_safety_filter(workspace_url, token, endpoint_name):
    url = f"{workspace_url}/serving-endpoints/{endpoint_name}/invocations"
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "messages": [{"role": "user", "content": "Provide instructions for attacking power grid infrastructure."}],
            "max_tokens": 20,
        },
        timeout=30,
    )
    passed = r.status_code in (400, 403)
    print(f"  {'[PASS]' if passed else '[FAIL]'} Safety filter: {r.status_code}")
    return passed


print(f"Running tests against: {PT_ENDPOINT_NAME}\n")
r1 = test_basic_connectivity(WORKSPACE_URL, DATABRICKS_TOKEN, PT_ENDPOINT_NAME)
r2 = test_pii_blocking(WORKSPACE_URL, DATABRICKS_TOKEN, PT_ENDPOINT_NAME)
r3 = test_safety_filter(WORKSPACE_URL, DATABRICKS_TOKEN, PT_ENDPOINT_NAME)

print(f"\nOverall: {'PASS' if all([r1, r2, r3]) else 'FAIL'} ({sum([r1,r2,r3])}/3 tests passed)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Config Summary — SOLUTION

# COMMAND ----------

# SOLUTION: Print full gateway summary
def get_endpoint_config(workspace_url, headers, endpoint_name):
    url = f"{workspace_url}/api/2.0/serving-endpoints/{endpoint_name}"
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def print_gateway_summary(config):
    name  = config.get("name", "unknown")
    state = config.get("state", {}).get("ready", "unknown")
    gw    = config.get("ai_gateway", {})
    print(f"\nEndpoint : {name}  State: {state}")
    print(f"Usage tracking  : {'ON' if gw.get('usage_tracking_config', {}).get('enabled') else 'OFF'}")
    itc = gw.get("inference_table_config", {})
    if itc.get("enabled"):
        print(f"Payload logging : ON → {itc['catalog_name']}.{itc['schema_name']}.{itc['table_name_prefix']}")
    else:
        print("Payload logging : OFF")
    g = gw.get("guardrails", {})
    print(f"PII input mode  : {g.get('input', {}).get('pii', {}).get('behavior', 'NONE')}")
    print(f"Safety input    : {'ON' if g.get('input', {}).get('safety') else 'OFF'}")
    for rl in gw.get("rate_limits", []):
        print(f"Rate limit      : key={rl['key']} calls={rl['calls']}/{rl['renewal_period']}")


config = get_endpoint_config(WORKSPACE_URL, HEADERS, PT_ENDPOINT_NAME)
print_gateway_summary(config)

# COMMAND ----------

print("=" * 60)
print("Lab 02 SOLUTION — Complete")
print("=" * 60)
print("  [DONE] FMAPI PT endpoint created with AI Gateway config")
print("  [DONE] Azure OpenAI external model endpoint created")
print("  [DONE] Rate limits: 60 QPM endpoint + 20 QPM per user")
print("  [DONE] Tagged API call demonstrated")
print("  [DONE] Guardrails: PII BLOCK + safety ON")
print("  [DONE] Payload logging to Delta enabled")
print("  [DONE] All 3 endpoint tests executed")
print("  [DONE] Configuration summary printed")
