from .models import DatasetSpec


class Status:
    COLLECTED = ("collected", "Records were collected successfully.")
    EMPTY = ("empty", "The source was accessible but returned no records in the requested time range.")
    PERMISSION_DENIED = ("permission_denied", "Access was denied. See required capability for the Snowflake role or account requirement.",)
    UNAVAILABLE_IN_ACCOUNT = ("unavailable_in_account", "This source or feature is not enabled or available in the account.",)
    UNSUPPORTED = ("unsupported","The source operation is unsupported by this account or Snowflake feature set.",)
    FAILED = ("failed", "Collection failed. The execution evidence records a sanitized error classification.",)

NORMALIZED_FIELD_DETAILS = {
    "platform": {"type": "string", "description": "Source platform."},
    "billing_account_id": {"type": "string", "description": "Snowflake organization name identifying the billing organization; FOCUS BillingAccountId takes precedence when provided."},
    "sub_account_id": {"type": "string", "description": "Snowflake account locator identifying the billed sub-account; source-provided SubAccountId or account locator takes precedence."},
    "source_category": {"type": "string", "description": "Connector source category."},
    "source_record_id": {"type": "string", "description": "Source row identifier."},
    "resource_id": {"type": "value", "description": "Source resource identifier."},
    "resource_name": {"type": "string", "description": "Source resource name."},
    "resource_type": {"type": "string", "description": "Source resource type."},
    "service_or_product": {"type": "string", "description": "Service or product dimension."},
    "sku": {"type": "string", "description": "Source SKU dimension."},
    "usage_start": {"type": "timestamp", "description": "Usage start, normalized to UTC."},
    "usage_end": {"type": "timestamp", "description": "Usage end, normalized to UTC."},
    "billing_period_start": {"type": "timestamp", "description": "Billing period start, normalized to UTC."},
    "billing_period_end": {"type": "timestamp", "description": "Billing period end, normalized to UTC."},
    "consumed_quantity": {"type": "decimal", "description": "Consumed quantity, preserving decimal precision."},
    "consumed_unit": {"type": "string", "description": "Unit for consumed quantity."},
    "pricing_quantity": {"type": "decimal", "description": "Quantity used for pricing."},
    "pricing_unit": {"type": "string", "description": "Unit for pricing quantity."},
    "list_unit_price": {"type": "decimal", "description": "List unit price."},
    "list_cost": {"type": "decimal", "description": "List cost."},
    "contracted_cost": {"type": "decimal", "description": "Contracted cost."},
    "effective_cost": {"type": "decimal", "description": "Effective cost."},
    "billed_cost": {"type": "decimal", "description": "Billed cost."},
    "currency": {"type": "string", "description": "ISO currency code when source-provided."},
    "tags_or_allocation_metadata": {"type": "value", "description": "Source allocation or tag value."},
    "source_update_time": {"type": "timestamp", "description": "Source update time, normalized to UTC."},
    "collection_time": {"type": "timestamp", "description": "Collection time, normalized to UTC."},
    "additional_source_metadata": {"type": "object", "description": "Unmapped non-null source fields; null only when no extra source values exist."},
}

DATASET_SPECS = (
    DatasetSpec("billing_spend", "Account-level daily metering and spend", "SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY", "usage_date", "usage_date"),
    DatasetSpec("compute_warehouse_consumption", "Warehouse credit consumption", "SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY", "start_time", "start_time"),
    DatasetSpec("compute_query_consumption", "Query-level compute metering", "SNOWFLAKE.ACCOUNT_USAGE.QUERY_METERING_HISTORY", "query_metering_hour", "query_metering_hour"),
    DatasetSpec("compute_all_resource_consumption", "Hourly warehouse, serverless, cloud-services, and Openflow credits", "SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY", "start_time", "start_time"),
    DatasetSpec("storage_consumption", "Account storage consumption", "SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE", "usage_date", "usage_date"),
    DatasetSpec("database_storage_consumption", "Database storage consumption", "SNOWFLAKE.ACCOUNT_USAGE.DATABASE_STORAGE_USAGE_HISTORY", "usage_date", "usage_date"),
    DatasetSpec("stage_storage_consumption", "Stage storage consumption", "SNOWFLAKE.ACCOUNT_USAGE.STAGE_STORAGE_USAGE_HISTORY", "usage_date", "usage_date"),
    DatasetSpec("storage_billed_history", "Billed database and stage storage history", "SNOWFLAKE.ACCOUNT_USAGE.STORAGE_DAILY_HISTORY", "usage_date", "usage_date"),
    DatasetSpec("storage_organization", "Organization-wide daily account storage", "SNOWFLAKE.ORGANIZATION_USAGE.ORGANIZATION_USAGE_STORAGE_HISTORY", "usage_date", "usage_date", "Organization account and GLOBALORGADMIN or SNOWFLAKE.ORGANIZATION_USAGE_VIEWER"),
    DatasetSpec("serverless_task_consumption", "Serverless task consumption", "SNOWFLAKE.ACCOUNT_USAGE.SERVERLESS_TASK_HISTORY", "start_time", "start_time"),
    DatasetSpec("serverless_alert_consumption", "Serverless alert consumption", "SNOWFLAKE.ACCOUNT_USAGE.SERVERLESS_ALERT_HISTORY", "start_time", "start_time"),
    DatasetSpec("managed_feature_consumption", "Managed feature and service consumption", "SNOWFLAKE.ACCOUNT_USAGE.SNOWPARK_CONTAINER_SERVICES_HISTORY", "start_time", "start_time"),
    DatasetSpec("serverless_clustering_consumption", "Automatic clustering credits", "SNOWFLAKE.ACCOUNT_USAGE.AUTOMATIC_CLUSTERING_HISTORY", "start_time", "start_time"),
    DatasetSpec("serverless_search_optimization_consumption", "Search optimization credits", "SNOWFLAKE.ACCOUNT_USAGE.SEARCH_OPTIMIZATION_HISTORY", "start_time", "start_time"),
    DatasetSpec("serverless_snowpipe_consumption", "Snowpipe credits and file ingestion history", "SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY", "start_time", "start_time"),
    DatasetSpec("serverless_cortex_ai_consumption", "Cortex AI feature usage", "SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY", "start_time", "start_time"),
    DatasetSpec("data_transfer_consumption", "Data transfer consumption", "SNOWFLAKE.ACCOUNT_USAGE.DATA_TRANSFER_HISTORY", "start_time", "start_time"),
    DatasetSpec("internal_data_transfer_consumption", "Internal data transfer consumption", "SNOWFLAKE.ACCOUNT_USAGE.INTERNAL_DATA_TRANSFER_HISTORY", "start_time", "start_time"),
    DatasetSpec("replication_consumption", "Database replication compute and transfer usage", "SNOWFLAKE.ACCOUNT_USAGE.DATABASE_REPLICATION_USAGE_HISTORY", "start_time", "start_time"),
    DatasetSpec("query_cost_attribution", "Query cost attribution", "SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY", "start_time", "start_time"),
    DatasetSpec("query_resource_usage", "Query execution and resource usage", "SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY", "start_time", "start_time"),
    DatasetSpec("pricing_rates_currency", "Organization rate and currency data", "SNOWFLAKE.ORGANIZATION_USAGE.RATE_SHEET_DAILY", "date", "date", "Organization account and ORGADMIN or GLOBALORGADMIN"),
    DatasetSpec("usage_in_currency", "Organization usage in currency", "SNOWFLAKE.ORGANIZATION_USAGE.USAGE_IN_CURRENCY_DAILY", "usage_date", "usage_date", "Organization account and ORGADMIN or GLOBALORGADMIN"),
    DatasetSpec("contracted_costs", "Contracted commitment terms, amount, and currency", "SNOWFLAKE.ORGANIZATION_USAGE.CONTRACT_ITEMS", "start_date", "start_date", "ORGANIZATION_BILLING_VIEWER or GLOBALORGADMIN"),
    DatasetSpec("commitments_balances", "Commitments and remaining balances", "SNOWFLAKE.ORGANIZATION_USAGE.REMAINING_BALANCE_DAILY", "date", "date", "ORGANIZATION_BILLING_VIEWER or GLOBALORGADMIN"),
    DatasetSpec("budgets_limits_monitors", "Budgets, limits, and resource monitors", "SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS", None, None, "SNOWFLAKE.OBJECT_VIEWER database role on SNOWFLAKE"),
    DatasetSpec("budget_spending_history", "Account budget credit spending history", "SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!GET_SPENDING_HISTORY", "time", "TIME", "Account budget enabled and SNOWFLAKE.BUDGET_VIEWER application role"),
    DatasetSpec("cost_anomalies", "Cost anomaly information", "SNOWFLAKE.ACCOUNT_USAGE.ANOMALIES_DAILY", "date", "date"),
    DatasetSpec("optimization_information", "Optimization and warehouse performance information", "SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY", "start_time", "start_time"),
    DatasetSpec("tags_allocation_metadata", "Tags and allocation metadata", "SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES", None, None, "SNOWFLAKE.GOVERNANCE_VIEWER database role on SNOWFLAKE"),
    DatasetSpec("focus_cost_usage", "FOCUS 1.3 daily charge line items with cost, quantity, account, and service dimensions", "SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3", "ChargePeriodStart", "ChargePeriodStart", "Organization-enabled account and SNOWFLAKE.ORGANIZATION_BILLING_VIEWER database role"),
)
