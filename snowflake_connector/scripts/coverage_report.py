"""Coverage report builders and writers."""

from typing import Any

from ..constants import Status
from ..models import CollectionResult
from ..utils import OutputWriter


def coverage_row(result: CollectionResult) -> dict[str, Any]:
    explanation = explanation_for(result)
    if result.status == Status.FAILED[0] and result.error and "Snowflake error 90073" in result.error:
        explanation = "Collection could not run because the configured warehouse was suspended after its resource monitor quota was exceeded."
    return {
        "category": result.spec.category,
        "dataset": result.spec.source,
        "purpose": result.spec.purpose,
        "status": result.status,
        "record_count": len(result.records),
        "earliest_source_timestamp": result.earliest_timestamp,
        "latest_source_timestamp": result.latest_timestamp,
        "required_capability": result.spec.capability,
        "explanation": explanation,
        "error_code": safe_error_code(result.error),
    }


def explanation_for(result: CollectionResult) -> str:
    return next(
        (item[1] for item in (
            Status.EMPTY,
            Status.PERMISSION_DENIED,
            Status.UNAVAILABLE_IN_ACCOUNT,
            Status.UNSUPPORTED,
            Status.FAILED,
            Status.COLLECTED,
        ) if item[0] == result.status),
        "Source returned an unrecognized collection status.",
    )


def safe_error_code(error: str | None) -> str | None:
    if not error:
        return None
    tokens = [part.strip() for part in error.split(";")]
    safe = [token for token in tokens if token.startswith(("Snowflake error ", "SQLSTATE "))]
    return "; ".join(safe) or "source error"


def coverage_markdown(rows: list[dict[str, Any]]) -> str:
    headings = ["Category", "Dataset", "Purpose", "Status", "Records", "Earliest timestamp", "Latest timestamp", "Required capability", "Explanation"]
    lines = ["# Snowflake collection coverage", "", "| " + " | ".join(headings) + " |", "|" + "|".join("---" for _ in headings) + "|"]
    for row in rows:
        values = [row["category"], row["dataset"], row["purpose"], row["status"], row["record_count"],
                  row["earliest_source_timestamp"] or "-", row["latest_source_timestamp"] or "-",
                  row["required_capability"] or "-", row["explanation"]]
        lines.append("| " + " | ".join(str(value).replace("|", "\\|").replace("\n", " ") for value in values) + " |")
    return "\n".join(lines) + "\n"


def write_coverage(output_dir, rows: list[dict[str, Any]]) -> None:
    folder = output_dir / "coverage"
    folder.mkdir(parents=True, exist_ok=True)
    writer = OutputWriter()
    writer.write_json(folder / "coverage_report.json", rows)
    writer.write_text(folder / "coverage_report.md", coverage_markdown(rows))
