"""Write discovered source schemas and normalized field definitions."""

from typing import Any

from ..constants import NORMALIZED_FIELD_DETAILS
from ..models import CollectionResult
from ..utils import OutputWriter


def build_schema_report(results: list[CollectionResult], connector) -> list[dict[str, Any]]:
    report = []
    for result in results:
        available = {column["name"].casefold() for column in (result.columns or [])}
        mappings = connector.normalizer.schema_mapper.mapping_for(result.spec.category)
        report.append({
            "category": result.spec.category,
            "dataset": result.spec.source,
            "columns": result.columns or [],
            "field_mappings": {
                field: {"source_column": column, "available_in_source": column.casefold() in available}
                for field, column in mappings.items()
            },
        })
    return report


def write_schema_outputs(output_dir, schemas: list[dict[str, Any]]) -> None:
    folder = output_dir / "schemas"
    folder.mkdir(parents=True, exist_ok=True)
    writer = OutputWriter()
    writer.write_json(folder / "dataset_schemas.json", schemas)
    writer.write_json(output_dir / "normalized_field_details.json", NORMALIZED_FIELD_DETAILS)
