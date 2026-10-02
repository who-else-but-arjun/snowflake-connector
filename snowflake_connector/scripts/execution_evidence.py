"""Redacted execution evidence builders and writers."""

from datetime import datetime
from typing import Any

from ..constants import Status
from ..utils import OutputWriter, Utils


def redact_identifier(value: Any) -> str | None:
    if value is None:
        return None
    account = str(value)
    return "***" if len(account) <= 5 else f"{account[:3]}...{account[-2:]}"


def build_evidence(context: dict[str, Any], start: datetime, end: datetime,
                   collection_time: datetime, rows: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = {status: {"datasets": 0, "records": 0} for status in (
        Status.COLLECTED[0], Status.EMPTY[0], Status.PERMISSION_DENIED[0], Status.UNAVAILABLE_IN_ACCOUNT[0],
        Status.UNSUPPORTED[0], Status.FAILED[0],
    )}
    for row in rows:
        statuses[row["status"]]["datasets"] += 1
        statuses[row["status"]]["records"] += row["record_count"]
    return {
        "authenticated": True,
        "account_redacted": redact_identifier(context.get("account")),
        "region": context.get("region"),
        "time_range_utc": f"[{Utils.as_utc(start).isoformat()}, {Utils.as_utc(end).isoformat()})",
        "collection_time_utc": Utils.as_utc(collection_time).isoformat(),
        "categories_investigated": len(rows),
        "status_counts": statuses,
        "categories": [
            {"category": row["category"], "dataset": row["dataset"], "status": row["status"],
             "record_count": row["record_count"], "error_code": row["error_code"]}
            for row in rows
        ],
    }


def evidence_text(evidence: dict[str, Any]) -> str:
    lines = [
        "Snowflake live execution evidence", "Authenticated: true",
        f"Account (redacted): {evidence['account_redacted']}", f"Region: {evidence['region']}",
        f"Time range UTC: {evidence['time_range_utc']}",
        f"Collection time UTC: {evidence['collection_time_utc']}",
        f"Categories investigated: {evidence['categories_investigated']}", "", "Status counts:",
    ]
    for status, counts in evidence["status_counts"].items():
        lines.append(f"{status}: {counts['datasets']} datasets, {counts['records']} records")
    lines.extend(["", "Per-category results:"])
    for row in evidence["categories"]:
        lines.append(f"{row['category']} ({row['dataset']}): {row['status']}, {row['record_count']} records")
    return "\n".join(lines) + "\n"


def write_evidence(output_dir, evidence: dict[str, Any]) -> None:
    folder = output_dir / "evidence"
    folder.mkdir(parents=True, exist_ok=True)
    writer = OutputWriter()
    writer.write_json(folder / "execution_evidence.json", evidence)
    writer.write_text(folder / "execution_evidence.txt", evidence_text(evidence))
