import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .constants import NORMALIZED_FIELD_DETAILS
from .utils import Utils


SCHEMA_CONFIGURATION = json.loads(
    Path(__file__).with_name("field_maps.json").read_text(encoding="utf-8")
)


class SchemaMapper:
    """Fill each normalized field from the category map, then overrides, then shared fallback chains."""

    CONFIG = SCHEMA_CONFIGURATION

    def mapping_for(self, category: str) -> dict[str, str]:
        """Return explicitly configured source columns for the schema report."""
        return self.CONFIG["field_maps"].get(category, {})

    def candidates(self, category: str, field: str) -> list[str]:
        """Ordered sources for a field: 'COLUMN', '@context_value' or '=literal'."""
        explicit = self.CONFIG["field_maps"].get(category, {}).get(field)
        overrides = self.CONFIG["overrides"].get(category, {}).get(field, [])
        return ([explicit] if explicit else []) + overrides + self.CONFIG["chains"].get(field, [])

    def map(self, category: str, record: dict[str, Any], context: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
        """Return the non-null mapped fields and the lowercase source columns that were used."""
        columns = {str(key).casefold(): value for key, value in record.items()}
        mapped: dict[str, Any] = {}
        used: set[str] = set()
        for field in NORMALIZED_FIELD_DETAILS:
            for source in self.candidates(category, field):
                if source.startswith("="):
                    value = source[1:]
                elif source.startswith("@"):
                    value = context.get(source)
                else:
                    value = columns.get(source.casefold())
                    if Utils.present(value):
                        used.add(source.casefold())
                if Utils.present(value):
                    mapped[field] = value
                    break
        unit = self.CONFIG["units"].get(category)
        defaults = {
            "resource_type": self.CONFIG["resource_types"].get(category),
            "consumed_unit": unit if "consumed_quantity" in mapped else None,
            "pricing_unit": unit if "pricing_quantity" in mapped else None,
        }
        for field, value in defaults.items():
            if value is not None:
                mapped.setdefault(field, value)
        return mapped, used


class CostNormalizer:
    """Convert raw Snowflake rows into the normalized cost schema."""

    def __init__(self) -> None:
        self.schema_mapper = SchemaMapper()

    def normalize(
        self,
        category: str,
        record: dict[str, Any] | None,
        collection_time: datetime,
        billing_account_id: str | None = None,
        sub_account_id: str | None = None,
    ) -> dict[str, Any]:
        """Normalize one source row; unavailable values stay null."""
        source_record = record or {}
        context = {"@account": sub_account_id, "@organization": billing_account_id, "@collection_time": collection_time}
        mapped, used_columns = self.schema_mapper.map(category, source_record, context)
        additional_metadata = self.additional_metadata(source_record, used_columns)
        normalized = {field: None for field in NORMALIZED_FIELD_DETAILS}
        normalized.update(
            {
                "platform": "snowflake",
                "billing_account_id": billing_account_id,
                "sub_account_id": sub_account_id,
                "source_category": category,
                **mapped,
                "collection_time": collection_time,
                "additional_source_metadata": additional_metadata,
            }
        )
        for field, details in NORMALIZED_FIELD_DETAILS.items():
            if details["type"] == "timestamp" and normalized[field] is not None:
                normalized[field] = Utils.as_utc(normalized[field])
        if normalized["source_record_id"] is None:
            normalized["source_record_id"] = Utils.rowKey(category, source_record)
        if normalized["usage_end"] is None and normalized["usage_start"] and category in SCHEMA_CONFIGURATION["date_grain"]:
            normalized["usage_end"] = normalized["usage_start"] + timedelta(days=1)
        return {key: Utils.json_value(value) for key, value in normalized.items()}

    @staticmethod
    def additional_metadata(record: Mapping[str, Any], mapped_columns: set[str]) -> dict[str, Any] | None:
        """Keep valid, unmapped source fields without duplicating mapped columns."""
        metadata = {}
        for key, value in record.items():
            if str(key).casefold() in mapped_columns or value is None:
                continue
            try:
                json.dumps(Utils.json_value(value), allow_nan=False)
            except (TypeError, ValueError):
                continue
            metadata[str(key)] = value
        return metadata or None

    def normalize_many(
        self,
        category: str,
        records: list[dict[str, Any]],
        collection_time: datetime,
        billing_account_id: str | None = None,
        sub_account_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Normalize each source row; an empty source produces an empty list."""
        return [
            self.normalize(category, record, collection_time, billing_account_id, sub_account_id)
            for record in records
        ]
