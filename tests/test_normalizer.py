from datetime import datetime, timezone
from decimal import Decimal

from snowflake_connector.constants import NORMALIZED_FIELD_DETAILS
from snowflake_connector.normalizer import CostNormalizer


def test_normalizer_preserves_decimal_precision_and_uses_utc():
    record = {
        "QUERY_ID": "query-1",
        "START_TIME": datetime(2026, 10, 1, 12, 0),
        "END_TIME": "2026-10-01T12:01:00+05:30",
        "CREDITS_USED": Decimal("0.0000012300"),
        "CURRENCY": "USD",
    }

    normalized = CostNormalizer().normalize(
        "compute_warehouse_consumption",
        record,
        datetime(2026, 10, 1, 13, 0, tzinfo=timezone.utc),
    )

    assert normalized["consumed_quantity"] == "0.0000012300"
    assert normalized["usage_start"] == "2026-10-01T12:00:00+00:00"
    assert normalized["usage_end"] == "2026-10-01T06:31:00+00:00"
    assert normalized["collection_time"] == "2026-10-01T13:00:00+00:00"


def test_normalizer_handles_malformed_source_record_without_inventing_values():
    normalized = CostNormalizer().normalize(
        "unknown_category",
        {"unexpected": object(), "BROKEN_TIME": "not-a-timestamp"},
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )

    assert normalized["platform"] == "snowflake"
    assert normalized["source_category"] == "unknown_category"
    assert normalized["usage_start"] is None
    assert normalized["billed_cost"] is None
    assert normalized["additional_source_metadata"] == {"BROKEN_TIME": "not-a-timestamp"}


def test_normalizer_treats_non_mapping_record_and_invalid_timestamp_as_nulls():
    normalizer = CostNormalizer()
    normalized = normalizer.normalize(
        "query_resource_usage",
        None,
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    invalid_timestamp = normalizer.normalize(
        "query_resource_usage",
        {"START_TIME": "not-a-time", "END_TIME": "also-not-a-time"},
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )

    assert normalized["source_record_id"] is None
    assert all(normalized[field] is None for field in ("usage_start", "consumed_quantity"))
    assert invalid_timestamp["usage_start"] is None
    assert invalid_timestamp["usage_end"] is None


def test_normalize_many_returns_empty_list_for_empty_source():
    assert CostNormalizer().normalize_many(
        "query_resource_usage", [], datetime(2026, 10, 1, tzinfo=timezone.utc)
    ) == []


def test_schema_mapper_maps_billing_fields_into_normalized_schema():
    normalized = CostNormalizer().normalize(
        "billing_spend",
        {
            "SERVICE_TYPE": "WAREHOUSE_METERING",
            "USAGE_DATE": "2026-10-01",
            "CREDITS_USED": Decimal("0.125000000"),
            "CREDITS_BILLED": Decimal("0.100000000"),
        },
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )

    assert normalized["service_or_product"] == "WAREHOUSE_METERING"
    assert normalized["consumed_quantity"] == "0.125000000"
    assert normalized["consumed_unit"] == "credits"
    assert normalized["pricing_quantity"] == "0.100000000"
    assert normalized["pricing_unit"] == "credits"


def test_schema_mapper_maps_storage_and_query_resource_fields():
    storage = CostNormalizer().normalize(
        "storage_consumption",
        {"USAGE_DATE": "2026-10-01", "STORAGE_BYTES": 2048},
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    query = CostNormalizer().normalize(
        "query_resource_usage",
        {"QUERY_ID": "query-1", "WAREHOUSE_NAME": "COMPUTE_WH", "BYTES_SCANNED": 4096, "START_TIME": "2026-10-01T00:00:00Z", "QUERY_TAG": "cost-center:finance"},
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )

    assert storage["consumed_quantity"] == 2048
    assert storage["consumed_unit"] == "bytes"
    assert query["source_record_id"] == "query-1"
    assert query["resource_name"] == "COMPUTE_WH"
    assert query["service_or_product"] is None
    assert query["consumed_quantity"] == 4096
    assert query["consumed_unit"] == "bytes"
    assert query["tags_or_allocation_metadata"] == "cost-center:finance"
    assert query["additional_source_metadata"] is None


def test_query_metering_maps_query_tag_and_retains_other_source_metadata():
    normalized = CostNormalizer().normalize(
        "compute_query_consumption",
        {"QUERY_ID": "q-3", "WAREHOUSE_ID": 7, "WAREHOUSE_NAME": "WH",
         "QUERY_START_TIME": "2026-10-01T00:00:00Z", "QUERY_END_TIME": "2026-10-01T00:00:01Z",
         "CREDITS_USED": Decimal("0.01"), "QUERY_TAG": "team:analytics", "USER_NAME": "ANALYST"},
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )

    assert normalized["source_record_id"] == "q-3"
    assert normalized["tags_or_allocation_metadata"] == "team:analytics"
    assert normalized["additional_source_metadata"] == {"USER_NAME": "ANALYST"}


def test_query_history_maps_query_type_and_empty_tag_to_null():
    normalized = CostNormalizer().normalize(
        "query_resource_usage",
        {"QUERY_ID": "query-2", "QUERY_TYPE": "SELECT", "QUERY_TAG": "  ",
         "BYTES_SCANNED": 0, "START_TIME": "2026-10-01T00:00:00Z"},
        datetime(2026, 10, 1, tzinfo=timezone.utc),
        billing_account_id="ACCT123",
        sub_account_id="LOC456",
    )

    assert normalized["billing_account_id"] == "ACCT123"
    assert normalized["sub_account_id"] == "LOC456"
    assert normalized["service_or_product"] == "SELECT"
    assert normalized["consumed_quantity"] == 0
    assert normalized["tags_or_allocation_metadata"] is None
    assert normalized["billed_cost"] is None
    assert normalized["billing_period_start"] is None


def test_normalized_output_contains_only_assessment_fields():
    normalized = CostNormalizer().normalize(
        "commitments_balances",
        {"DATE": "2026-10-01", "CURRENCY": "USD", "CAPACITY_BALANCE": Decimal("12.50")},
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )

    assert tuple(normalized) == tuple(NORMALIZED_FIELD_DETAILS)
    assert normalized["consumed_quantity"] is None
    assert normalized["additional_source_metadata"] == {"CAPACITY_BALANCE": "12.50"}


def test_explicit_dataset_mappings_use_source_columns_without_fallbacks():
    normalized = CostNormalizer().normalize(
        "compute_all_resource_consumption",
        {
            "ENTITY_ID": 12,
            "ENTITY_TYPE": "TASK",
            "NAME": "TASK_A",
            "SERVICE_TYPE": "SERVERLESS_TASK",
            "START_TIME": "2026-10-01T00:00:00Z",
            "END_TIME": "2026-10-01T00:01:00Z",
            "CREDITS_USED": Decimal("0.25"),
            "RESOURCE_ID": 99,
        },
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )

    assert normalized["resource_id"] == 12
    assert normalized["resource_name"] == "TASK_A"
    assert normalized["resource_type"] == "TASK"
    assert normalized["consumed_quantity"] == "0.25"
    assert normalized["additional_source_metadata"] == {"RESOURCE_ID": 99}


def test_rate_sheet_maps_effective_rate_to_list_unit_price_without_metadata_blob():
    normalized = CostNormalizer().normalize(
        "pricing_rates_currency",
        {"ACCOUNT_LOCATOR": "LOC123", "SERVICE_TYPE": "WAREHOUSE_METERING",
         "DATE": "2026-10-01", "CURRENCY": "USD", "EFFECTIVE_RATE": Decimal("2.500000")},
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )

    assert normalized["sub_account_id"] == "LOC123"
    assert normalized["service_or_product"] == "WAREHOUSE_METERING"
    assert normalized["list_unit_price"] == "2.500000"
    assert normalized["additional_source_metadata"] is None


def test_contract_amount_maps_to_contracted_cost_without_renaming_price_rate():
    normalized = CostNormalizer().normalize(
        "contracted_costs",
        {"CONTRACT_ITEM": "CAPACITY", "AMOUNT": Decimal("1250.00"), "CURRENCY": "USD"},
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )

    assert normalized["contracted_cost"] == "1250.00"
    assert normalized["currency"] == "USD"
    assert normalized["list_unit_price"] is None
