import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from snowflake_connector.normalizer import SchemaMapper
from snowflake_connector.utils import Utils


def test_public_value_helpers_handle_missing_decimal_and_timestamp_values():
    assert Utils.firstValue(None, "  ", "value") == "value"
    assert not Utils.present(float("nan"))
    assert Utils.decimalValue("0.0000012300") == Decimal("0.0000012300")
    assert Utils.decimalValue(True) is None
    assert Utils.formatDecimal(Decimal("1.2")) == "1.200000000"
    assert Utils.asDatetime(date(2026, 10, 1)) == datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert Utils.asDatetime("invalid") is None


def test_row_key_is_stable_for_equivalent_source_records():
    assert Utils.rowKey("usage", {"a": 1, "b": 2}) == Utils.rowKey("usage", {"b": 2, "a": 1})


def test_schema_mapper_loads_field_mappings_from_json():
    mapping_file = Path(__file__).parents[1] / "snowflake_connector" / "field_maps.json"

    configuration = json.loads(mapping_file.read_text(encoding="utf-8"))
    assert configuration["categories"] == SchemaMapper.CATEGORY_CONFIGURATIONS
    assert SchemaMapper.mapping_for("query_resource_usage")["consumed_quantity"] == "BYTES_SCANNED"
