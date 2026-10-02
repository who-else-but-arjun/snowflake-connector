from datetime import datetime, timezone

from snowflake_connector.constants import Status
from snowflake_connector.models import CollectionResult, DatasetSpec
from snowflake_connector.scripts.coverage_report import coverage_row
from snowflake_connector.scripts.execution_evidence import build_evidence


def test_coverage_reports_empty_and_permission_states_without_source_text():
    spec = DatasetSpec("focus", "FOCUS billing lines", "SNOWFLAKE.BILLING.FOCUS", None, None, "Organization billing role")
    denied = CollectionResult(spec, Status.PERMISSION_DENIED[0], [], "SQLSTATE 42501; sensitive query text")
    empty = CollectionResult(spec, Status.EMPTY[0], [])

    denied_row = coverage_row(denied)
    empty_row = coverage_row(empty)

    assert denied_row["status"] == "permission_denied"
    assert denied_row["required_capability"] == "Organization billing role"
    assert denied_row["error_code"] == "SQLSTATE 42501"
    assert "sensitive" not in str(denied_row)
    assert empty_row["status"] == "empty"
    assert empty_row["record_count"] == 0
    assert "accessible" in empty_row["explanation"]


def test_coverage_explains_resource_monitor_block_without_leaking_names():
    spec = DatasetSpec("query", "Query rows", "SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY", None, None)
    failure = CollectionResult(
        spec, Status.FAILED[0], [],
        "Snowflake error 90073; SQLSTATE 22000; Warehouse 'SECRET_WH' monitor 'SECRET_MONITOR' exceeded quota",
    )

    row = coverage_row(failure)

    assert "resource monitor quota was exceeded" in row["explanation"]
    assert row["error_code"] == "Snowflake error 90073; SQLSTATE 22000"
    assert "SECRET" not in str(row)


def test_execution_evidence_redacts_account_and_counts_all_statuses():
    at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    evidence = build_evidence(
        {"account": "ACCOUNT-123456", "region": "AWS_US_EAST_1", "user": "private@example.com"},
        at,
        datetime(2026, 10, 2, tzinfo=timezone.utc),
        at,
        [
            {"category": "billing", "dataset": "source_a", "status": Status.COLLECTED[0], "record_count": 2, "error_code": None},
            {"category": "focus", "dataset": "source_b", "status": Status.PERMISSION_DENIED[0], "record_count": 0, "error_code": "SQLSTATE 42501"},
        ],
    )

    assert evidence["authenticated"] is True
    assert evidence["account_redacted"] != "ACCOUNT-123456"
    assert evidence["region"] == "AWS_US_EAST_1"
    assert evidence["status_counts"][Status.COLLECTED[0]] == {"datasets": 1, "records": 2}
    assert evidence["status_counts"][Status.PERMISSION_DENIED[0]] == {"datasets": 1, "records": 0}
    assert "private@example.com" not in str(evidence)
