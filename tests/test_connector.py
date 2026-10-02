import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from snowflake_connector.connector import SnowflakeCostConnector
from snowflake_connector.exceptions import AuthenticationError
from snowflake_connector.models import ConnectorConfig, DatasetSpec
from snowflake_connector.utils import OutputWriter, Utils


class FakeCursor:
    def __init__(self, columns, batches=None, error=None, context=None, column_types=None):
        self.description = [(column,) for column in columns]
        self.columns = list(columns)
        self.column_types = column_types or {}
        self.data_batches = list(batches or [])
        self.batches = list(self.data_batches)
        self.error = error
        self.context = context or {}
        self.queries = []

    def execute(self, query, parameters=()):
        self.queries.append((query, parameters))
        if self.error and not query.startswith("SELECT CURRENT_ACCOUNT"):
            raise self.error
        if query.startswith("DESC VIEW"):
            self.description = [("name",)]
            self.batches = [[(column, self.column_types.get(column), None, None, None, None, None, None, None, None) for column in self.columns]]
        elif query.startswith("SELECT ") and not query.startswith("SELECT CURRENT_ACCOUNT"):
            self.description = [(column,) for column in self.columns]
            self.batches = list(self.data_batches)

    def fetchmany(self, size):
        return self.batches.pop(0) if self.batches else []

    def fetchone(self):
        return tuple(self.context.get(key) for key in ("account", "organization", "region", "user", "role", "warehouse"))

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor

    def cursor(self):
        return self.cursor_value

    def close(self):
        pass


def connector_with_cursor(cursor):
    connector = SnowflakeCostConnector(
        ConnectorConfig("account", "user", "password", None, None, None, "ACCOUNTADMIN", None),
        connection_factory=lambda **kwargs: FakeConnection(cursor),
        batch_size=2,
    )
    connector.connect()
    return connector


def test_collection_reads_all_batches_and_applies_time_parameters():
    cursor = FakeCursor(
        ["QUERY_ID", "START_TIME", "CREDITS_USED"],
        batches=[
            [("q1", datetime(2026, 10, 1, tzinfo=timezone.utc), Decimal("0.1"))],
            [("q2", datetime(2026, 10, 2, tzinfo=timezone.utc), Decimal("0.2"))],
        ],
        context={"account": "account", "region": "region", "user": "user", "role": "ACCOUNTADMIN", "warehouse": "COMPUTE_WH"},
    )
    connector = connector_with_cursor(cursor)
    spec = DatasetSpec("test", "test", "SNOWFLAKE.ACCOUNT_USAGE.TEST", "start_time", "start_time")

    result = connector.collect_dataset(spec, datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 10, 3, tzinfo=timezone.utc))

    assert result.status == "collected"
    assert len(result.records) == 2
    assert result.records[0]["CREDITS_USED"] == Decimal("0.1")
    assert cursor.queries[-1][1][0].year == 2026


def test_collection_caps_rows_per_category_at_configured_maximum():
    cursor = FakeCursor(
        ["ID", "START_TIME"],
        batches=[[(index, datetime(2026, 10, 1, tzinfo=timezone.utc)) for index in range(250)]],
        context={"account": "account", "region": "region", "user": "user", "role": "ACCOUNTADMIN", "warehouse": "COMPUTE_WH"},
    )
    connector = connector_with_cursor(cursor)
    spec = DatasetSpec("limited", "limited test source", "SNOWFLAKE.ACCOUNT_USAGE.LIMITED", "start_time", "start_time")

    result = connector.collect_dataset(spec, datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 10, 2, tzinfo=timezone.utc))

    assert len(result.records) == 200
    assert "LIMIT 200" in cursor.queries[-1][0]


def test_date_sources_include_the_utc_day_overlapped_by_a_partial_window():
    cursor = FakeCursor(
        ["USAGE_DATE"],
        batches=[[(date(2026, 10, 1),)]],
        context={"account": "account", "region": "region", "user": "user", "role": "ACCOUNTADMIN", "warehouse": "COMPUTE_WH"},
        column_types={"USAGE_DATE": "DATE"},
    )
    connector = connector_with_cursor(cursor)
    spec = DatasetSpec("daily", "Daily data", "SNOWFLAKE.ACCOUNT_USAGE.DAILY", "usage_date", "usage_date")

    result = connector.collect_dataset(
        spec,
        datetime(2026, 10, 1, 15, tzinfo=timezone.utc),
        datetime(2026, 10, 1, 16, tzinfo=timezone.utc),
    )

    assert result.status == "collected"
    assert cursor.queries[-1][1] == (date(2026, 10, 1), date(2026, 10, 2))


def test_focus_cost_lines_are_filtered_by_charge_period_overlap():
    cursor = FakeCursor(
        ["ChargePeriodStart", "ChargePeriodEnd", "BilledCost"],
        batches=[[(datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 10, 2, tzinfo=timezone.utc), Decimal("2.50"))]],
        context={"account": "account", "region": "region", "user": "user", "role": "ACCOUNTADMIN", "warehouse": "COMPUTE_WH"},
    )
    connector = connector_with_cursor(cursor)
    spec = DatasetSpec("focus_cost_usage", "FOCUS costs", "SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3", "ChargePeriodStart", "ChargePeriodStart")
    start = datetime(2026, 10, 1, 15, tzinfo=timezone.utc)
    end = datetime(2026, 10, 1, 16, tzinfo=timezone.utc)

    result = connector.collect_dataset(spec, start, end)

    query, parameters = cursor.queries[-1]
    assert result.status == "collected"
    assert '"ChargePeriodStart" < %s AND "ChargePeriodEnd" > %s' in query
    assert parameters == (end, start)


def test_empty_results_are_reported_as_empty():
    cursor = FakeCursor(
        ["ID"],
        batches=[],
        context={"account": "account", "region": "region", "user": "user", "role": "ACCOUNTADMIN", "warehouse": "COMPUTE_WH"},
    )
    connector = connector_with_cursor(cursor)
    spec = DatasetSpec("empty", "empty", "SNOWFLAKE.ACCOUNT_USAGE.EMPTY", None, None)

    result = connector.collect_dataset(spec, datetime.now(timezone.utc), datetime.now(timezone.utc))

    assert result.status == "empty"
    assert result.records == []


def test_permission_failures_are_distinguished():
    class PrivilegeError(RuntimeError):
        sqlstate = "42501"

    cursor = FakeCursor(
        ["ID"],
        error=PrivilegeError("Snowflake SQL access control error"),
        context={"account": "account", "region": "region", "user": "user", "role": "ACCOUNTADMIN", "warehouse": "COMPUTE_WH"},
    )
    connector = connector_with_cursor(cursor)
    spec = DatasetSpec("denied", "denied", "SNOWFLAKE.ORGANIZATION_USAGE.TEST", None, None, "Organization usage access")

    result = connector.collect_dataset(spec, datetime.now(timezone.utc), datetime.now(timezone.utc))

    assert result.status == "permission_denied"
    assert result.error


def test_ambiguous_missing_or_unauthorized_object_is_not_guessed():
    class AmbiguousObjectError(RuntimeError):
        errno = 2003
        sqlstate = "02000"

    assert Utils.classify_error(AmbiguousObjectError("object does not exist or not authorized")) == "failed"


def test_inactive_snowflake_account_budget_is_unavailable():
    class InactiveBudgetError(RuntimeError):
        errno = -20000
        sqlstate = "P0001"
        raw_msg = "Uncaught exception of type 'ACCOUNT_ROOT_BUDGET_NOT_ACTIVATED'"

    assert Utils.classify_error(InactiveBudgetError()) == "unavailable_in_account"


def test_authentication_failures_raise_specific_error():
    def failing_factory(**kwargs):
        raise RuntimeError("390100 authentication failed")

    connector = SnowflakeCostConnector(ConnectorConfig("account", "user", "bad", None, None, None, None, None), failing_factory)

    with pytest.raises(AuthenticationError):
        connector.connect()


def test_environment_configuration_loads_dotenv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for key in ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text("SNOWFLAKE_ACCOUNT=dotenv-account\nSNOWFLAKE_USER=dotenv-user\nSNOWFLAKE_PASSWORD=dotenv-password\n", encoding="utf-8")

    connector = SnowflakeCostConnector.from_environment()

    assert connector.config.account == "dotenv-account"
    assert connector.config.user == "dotenv-user"
    assert connector.config.password == "dotenv-password"


def test_output_writer_preserves_nested_raw_records_as_json(tmp_path):
    OutputWriter().write_json(
        tmp_path / "raw_records.json",
        [{"source_category": "billing", "source_dataset": "source", "record": {"COST": "0.000000001"}}],
    )

    content = (tmp_path / "raw_records.json").read_text(encoding="utf-8")

    assert '"COST": "0.000000001"' in content
    assert "0.000000001" in content



def test_collection_returns_raw_and_normalized_data_without_writing_files(tmp_path, monkeypatch):
    cursor = FakeCursor(
        ["QUERY_ID", "START_TIME", "CREDITS_USED"],
        batches=[[ ("query-1", datetime(2026, 10, 1, tzinfo=timezone.utc), Decimal("0.500000")) ]],
        context={"account": "KX09510", "organization": "YLKGDMX", "region": "region", "user": "user", "role": "ACCOUNTADMIN", "warehouse": "COMPUTE_WH"},
    )
    connector = connector_with_cursor(cursor)
    spec = DatasetSpec("compute_query_consumption", "Query compute", "SNOWFLAKE.ACCOUNT_USAGE.QUERY_METERING_HISTORY", "start_time", "start_time")
    monkeypatch.setattr("snowflake_connector.connector.DATASET_SPECS", (spec,))

    result = connector.collect(datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 10, 2, tzinfo=timezone.utc))

    assert set(result) == {"raw_records", "normalized_records"}
    assert len(result["raw_records"]) == len(result["normalized_records"]) == 1
    assert result["normalized_records"][0]["consumed_quantity"] == "0.500000"
    assert result["normalized_records"][0]["billing_account_id"] == "YLKGDMX"
    assert result["normalized_records"][0]["sub_account_id"] == "KX09510"
    assert not list(tmp_path.iterdir())
