"""Run one live collection and generate each assessment output file."""

from datetime import datetime
from pathlib import Path
from typing import Any

from ..constants import DATASET_SPECS
from ..connector import SnowflakeCostConnector
from .coverage_report import coverage_row, write_coverage
from .execution_evidence import build_evidence, write_evidence
from .normalized_output import write_normalized_records
from .raw_output import write_raw_records
from .schema_output import build_schema_report, write_schema_outputs


def generate_outputs(connector: SnowflakeCostConnector, start: datetime, end: datetime,
                    output_dir: Path) -> dict[str, Any]:
    """Collect all datasets once and delegate each artifact to its output script."""
    if start >= end:
        raise ValueError("start must be earlier than end")
    context = connector.account_context() if connector.connection is not None else connector.connect()
    connector.execute("ALTER SESSION SET TIMEZONE = 'UTC'")
    collection_time = connector.utils.utc_now()
    results = [connector.collect_dataset(spec, start, end) for spec in DATASET_SPECS]

    raw_records = [
        {"source_category": result.spec.category, "source_dataset": result.spec.source, "record": record}
        for result in results for record in result.records
    ]
    normalized_records = [
        normalized
        for result in results
        for normalized in connector.normalizer.normalize_many(
            result.spec.category, result.records, collection_time,
            context.get("organization"), context.get("account")
        )
    ]
    coverage = [coverage_row(result) for result in results]
    schemas = build_schema_report(results, connector)
    evidence = build_evidence(context, start, end, collection_time, coverage)

    write_raw_records(output_dir, raw_records)
    write_normalized_records(output_dir, normalized_records)
    write_coverage(output_dir, coverage)
    write_evidence(output_dir, evidence)
    write_schema_outputs(output_dir, schemas)
    return {"raw_records": raw_records, "normalized_records": normalized_records,
            "coverage": coverage, "execution_evidence": evidence}
