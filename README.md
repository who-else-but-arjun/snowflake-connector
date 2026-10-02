# Snowflake Cost Connector

A Python connector for discovering, collecting, and normalizing Snowflake cost and usage sources. The connector returns raw and normalized records; the command-line reporting layer writes the assessment artifacts locally.

## Prerequisites

- A Snowflake account and a role that can read the relevant `SNOWFLAKE` shared database views.
- Organization billing sources require an organization-enabled account and the appropriate organization role. The FOCUS source is `SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3`; Snowflake documents that it requires `SNOWFLAKE.ORGANIZATION_BILLING_VIEWER` on an org-enabled account.

## Install

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `SNOWFLAKE_ACCOUNT` and `SNOWFLAKE_USER` in `.env`, then configure password or SSO authentication. For password authentication set `SNOWFLAKE_PASSWORD`; for SSO set `SNOWFLAKE_AUTHENTICATOR=externalbrowser`. Warehouse, role, database, schema, and authenticator are optional. Keep `.env` private; the checked-in example contains placeholders only.

## Run

```powershell
python -m snowflake_connector `
  --start 2026-10-01T00:00:00Z `
  --end 2026-10-02T00:00:00Z `
  --output-dir output `
  --max-records-per-category 200
```

The time window uses `start` inclusive and `end` exclusive for timestamp columns. FOCUS charge periods are filtered by overlap with the requested window. For date-grain sources, the collector queries the dates touched by the window. ISO timestamps without an offset are treated as UTC. The collector sets the Snowflake session timezone to UTC, discovers source columns, selects them explicitly, and reads result batches up to the per-category record cap. It continues across optional-source failures. The connector issues read-only queries; it does not create or modify Snowflake tables or data. Query execution can consume warehouse resources.

Output code is in `snowflake_connector/scripts/`: `generate_outputs.py` coordinates one collection; `raw_output.py`, `normalized_output.py`, `coverage_report.py`, `execution_evidence.py`, and `schema_output.py` each write their corresponding output type. No sample-output files are generated.

## Generated deliverables

- `output/raw/raw_records.json`: all collected source rows, each paired with its category and source view.
- `output/normalized/normalized_records.json`: normalized rows, using the assessment fields. Decimal precision is preserved; timestamps are UTC. Unmapped source columns are retained under `additional_source_metadata` without duplicating fields already mapped to the normalized schema.
- `output/coverage/coverage_report.md` and `coverage_report.json`: one row per investigated category with status, record count, timestamp bounds, capability, and explanation.
- `output/evidence/execution_evidence.txt` and `execution_evidence.json`: redacted live authentication, account and region, time window, collection time, statuses, and counts. No credentials, user identity, or query text are included.
- `output/schemas/dataset_schemas.json`: discovered columns and declared normalized mappings.
- `output/normalized_field_details.json`: normalized field types and descriptions.

An empty source contributes no raw or normalized rows. Collection errors are classified internally as permission denied, unsupported, unavailable in the account, or failed; authentication errors are raised as `AuthenticationError`. Snowflake error 002003 can mean either an absent object or missing privilege, so it remains an ambiguous failure.

## Coverage inventory

The collector attempts the following categories. Some Account Usage sources need the `SNOWFLAKE.USAGE_VIEWER` database role; object and tag metadata may need `OBJECT_VIEWER` or `GOVERNANCE_VIEWER`. Organization sources and FOCUS have separate organization requirements. Actual columns and Snowflake types are recorded in `output/schemas/dataset_schemas.json`.

| Category | Source | Purpose |
|---|---|---|
| Billing and spend | `ACCOUNT_USAGE.METERING_DAILY_HISTORY` | Daily compute credits used, adjusted, and billed |
| Warehouse compute | `ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY` | Hourly warehouse credit use |
| Query metering | `ACCOUNT_USAGE.QUERY_METERING_HISTORY` | Query-level credit use |
| Compute | `ACCOUNT_USAGE.METERING_HISTORY` | Hourly warehouse, serverless, cloud-service, and Openflow use |
| Storage | `ACCOUNT_USAGE.STORAGE_USAGE` | Daily account database and stage bytes |
| Database storage | `ACCOUNT_USAGE.DATABASE_STORAGE_USAGE_HISTORY` | Average database storage bytes |
| Stage storage | `ACCOUNT_USAGE.STAGE_STORAGE_USAGE_HISTORY` | Average stage storage bytes |
| Billed storage | `ACCOUNT_USAGE.STORAGE_DAILY_HISTORY` | Account storage measures closer to billed storage |
| Organization storage | `ORGANIZATION_USAGE.ORGANIZATION_USAGE_STORAGE_HISTORY` | Daily storage by organization account |
| Serverless tasks and alerts | `ACCOUNT_USAGE.SERVERLESS_TASK_HISTORY`, `SERVERLESS_ALERT_HISTORY` | Managed task and alert credits |
| Managed feature compute | `ACCOUNT_USAGE.SNOWPARK_CONTAINER_SERVICES_HISTORY` | Container service usage |
| Automatic clustering | `ACCOUNT_USAGE.AUTOMATIC_CLUSTERING_HISTORY` | Clustering credits |
| Search optimization | `ACCOUNT_USAGE.SEARCH_OPTIMIZATION_HISTORY` | Search optimization credits |
| Snowpipe | `ACCOUNT_USAGE.PIPE_USAGE_HISTORY` | Snowpipe usage history |
| Cortex AI | `ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY` | Cortex AI functions usage |
| Data transfer | `ACCOUNT_USAGE.DATA_TRANSFER_HISTORY`, `INTERNAL_DATA_TRANSFER_HISTORY` | External and internal transfer usage |
| Replication | `ACCOUNT_USAGE.DATABASE_REPLICATION_USAGE_HISTORY` | Replication credits and bytes |
| Query attribution | `ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY` | Compute credits attributed to queries |
| Query resources | `ACCOUNT_USAGE.QUERY_HISTORY` | Query timing, resource, and scan measures |
| Pricing and rates | `ORGANIZATION_USAGE.RATE_SHEET_DAILY` | Effective rates and billing dimensions |
| Currency spend | `ORGANIZATION_USAGE.USAGE_IN_CURRENCY_DAILY` | Daily usage quantity, billed amount, currency, and funding source |
| Contract terms | `ORGANIZATION_USAGE.CONTRACT_ITEMS` | Contract item, term dates, amount, and currency |
| Commitments and balance | `ORGANIZATION_USAGE.REMAINING_BALANCE_DAILY` | Free, capacity, rollover, and on-demand balances |
| Resource monitors | `ACCOUNT_USAGE.RESOURCE_MONITORS` | Monitor thresholds and configuration |
| Budget spending | `SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!GET_SPENDING_HISTORY` | Account budget spending history using Snowflake's budget method |
| Anomalies | `ACCOUNT_USAGE.ANOMALIES_DAILY` | Daily usage anomalies |
| Optimization | `ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY` | Warehouse load and queueing for tuning |
| Tags and allocation | `ACCOUNT_USAGE.TAG_REFERENCES` | Object tag references used for allocation joins |
| FOCUS | `SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3` | FOCUS 1.3 daily charge lines |


## Normalized schema and mapping

`snowflake_connector/field_maps.json` contains direct field mappings, category overrides, shared fallback candidates, units, resource types, and date-grain categories. `SchemaMapper` is defined in `normalizer.py`; it checks the category mapping, category override, then shared candidates. Context candidates can use the current organization, account locator, or collection time. For date-grain categories, it sets `usage_end` to one day after `usage_start` when no end is provided. Category configuration supplies known units and resource types. Shared value parsing, timestamp conversion, JSON conversion, and row-key helpers live on `Utils`. Source columns with no normalized field remain in `additional_source_metadata`; columns used for mapped fields are excluded from it. The CLI limits collection to 200 rows per category by default; `--max-records-per-category` changes the limit. Decimal values are serialized as strings to preserve precision; timestamps are normalized to UTC. Source-provided FOCUS account identifiers take precedence over live account context.

| Field | Meaning |
|---|---|
| `platform` | Cloud/service platform (`snowflake`). |
| `billing_account_id`, `sub_account_id` | Billing organization and child account identifiers when source-provided. |
| `source_category`, `source_record_id` | Connector source category and source row identifier; a stable hash is generated if the source omits an ID. |
| `resource_id`, `resource_name`, `resource_type` | Source resource identity and kind. |
| `service_or_product`, `sku` | Service/product and SKU dimensions. |
| `usage_start`, `usage_end` | Usage interval in UTC. |
| `billing_period_start`, `billing_period_end` | Billing interval in UTC. |
| `consumed_quantity`, `consumed_unit` | Source-metered quantity and source unit. |
| `pricing_quantity`, `pricing_unit` | Quantity used for pricing and its unit. |
| `list_unit_price`, `list_cost`, `contracted_cost`, `effective_cost`, `billed_cost` | Cost fields only when an explicitly mapped source provides them. |
| `currency` | Source currency code. |
| `tags_or_allocation_metadata` | Source allocation/tag value, when present. |
| `source_update_time`, `collection_time` | Source update timestamp when available, configured collection-time fallback, and UTC collection timestamp. |
| `additional_source_metadata` | Non-null source columns with no direct normalized field, when present. |

Snowflake view availability and columns can depend on account type, release, and role; the live schema output is the authority for each run.

## Tests and reproducibility

Run offline tests without Snowflake credentials:

```powershell
python -m pytest -q
```

The tests use synthetic cursor fixtures and cover batching, time filtering, empty data, access denial, authentication failure, timestamp normalization, malformed records, exact source mapping, decimal precision, coverage, and evidence redaction. Tests do not need Snowflake credentials. For consistent setup, use the pinned packages in `requirements.txt` and run the command above from the project directory.

