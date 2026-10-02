import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from .constants import DATASET_SPECS, Status
from .exceptions import AuthenticationError
from .models import CollectionResult, ConnectorConfig, DatasetSpec
from .normalizer import CostNormalizer
from .utils import Utils


class SnowflakeCostConnector:
    """Fetch raw Snowflake rows and return their normalized equivalents."""

    def __init__(self, config: ConnectorConfig, connection_factory: Callable[..., Any] | None = None,
                 batch_size: int = 1000, max_records_per_category: int = 200):
        """Create a connector with credentials, an optional connection factory, and batch size."""
        self.config = config
        self.connection_factory = connection_factory
        self.batch_size = batch_size
        if max_records_per_category < 1:
            raise ValueError("max_records_per_category must be at least 1")
        self.max_records_per_category = max_records_per_category
        self.connection: Any = None
        self.normalizer = CostNormalizer()
        self.utils = Utils()

    @classmethod
    def from_environment(cls, environ: dict[str, str] | None = None,
                         max_records_per_category: int = 200) -> "SnowflakeCostConnector":
        """Build the connector from environment variables and an optional local .env file."""
        if environ is None:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=Path.cwd() / ".env")
            values = os.environ
        else:
            values = environ
        account = values.get("SNOWFLAKE_ACCOUNT", "").strip()
        user = values.get("SNOWFLAKE_USER", "").strip()
        if not account or not user:
            raise ValueError("SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER are required")
        config = ConnectorConfig(
            account=account,
            user=user,
            password=values.get("SNOWFLAKE_PASSWORD"),
            warehouse=values.get("SNOWFLAKE_WAREHOUSE"),
            database=values.get("SNOWFLAKE_DATABASE"),
            schema=values.get("SNOWFLAKE_SCHEMA"),
            role=values.get("SNOWFLAKE_ROLE"),
            authenticator=values.get("SNOWFLAKE_AUTHENTICATOR"),
        )
        return cls(config, max_records_per_category=max_records_per_category)

    def connect(self) -> dict[str, Any]:
        """Open Snowflake and return account context needed for execution evidence."""
        if self.connection_factory is None:
            import snowflake.connector

            self.connection_factory = snowflake.connector.connect
        parameters = {key: value for key, value in {
            "account": self.config.account,
            "user": self.config.user,
            "password": self.config.password,
            "warehouse": self.config.warehouse,
            "database": self.config.database,
            "schema": self.config.schema,
            "role": self.config.role,
            "authenticator": self.config.authenticator,
        }.items() if value}
        try:
            self.connection = self.connection_factory(**parameters)
            return self.account_context()
        except Exception as error:
            raise AuthenticationError(str(error)) from error

    def collect(self, start: datetime, end: datetime) -> dict[str, list[dict[str, Any]]]:
        """Collect source rows and normalized rows; callers own all output writing."""
        if start >= end:
            raise ValueError("start must be earlier than end")
        if self.connection is None:
            self.connect()
        collection_time = self.utils.utc_now()
        context = self.account_context()
        self.execute("ALTER SESSION SET TIMEZONE = 'UTC'")
        results = [self.collect_dataset(spec, start, end) for spec in DATASET_SPECS]
        raw_records = [
            {
                "source_category": result.spec.category,
                "source_dataset": result.spec.source,
                "record": record,
            }
            for result in results
            for record in result.records
        ]
        normalized_records = [
            normalized
            for result in results
            for normalized in self.normalizer.normalize_many(
                result.spec.category, result.records, collection_time,
                context.get("organization"), context.get("account")
            )
        ]
        return {"raw_records": raw_records, "normalized_records": normalized_records}

    def close(self) -> None:
        """Close the current Snowflake connection."""
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def collect_dataset(self, spec: DatasetSpec, start: datetime, end: datetime) -> CollectionResult:
        """Describe one view, collect its bounded result batches, and classify failures."""
        cursor = None
        column_details = None
        try:
            cursor = self.connection.cursor()
            if spec.category == "budget_spending_history":
                return self.collect_budget_result(cursor, spec, start, end)
            column_details = self.describe_view_columns(cursor, spec.source)
            query, parameters = self.build_view_query(spec, column_details, start, end)
            records = self.fetch_records(cursor, query, parameters)
            return self.collection_result(spec, records, column_details)
        except Exception as error:
            return CollectionResult(spec, self.utils.classify_error(error), [], self.utils.safe_error(error), columns=column_details)
        finally:
            if cursor is not None:
                cursor.close()

    def collect_budget_result(self, cursor: Any, spec: DatasetSpec, start: datetime, end: datetime) -> CollectionResult:
        """Call the account budget spending-history method and wrap its result set."""
        call = "CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!GET_SPENDING_HISTORY(TIME_LOWER_BOUND => %s, TIME_UPPER_BOUND => %s)"
        cursor.execute(call, (start, end))
        if not cursor.description:
            raise RuntimeError("Snowflake budget method returned no tabular result set")
        columns = [description[0] for description in cursor.description]
        records = self.fetch_current_result(cursor, columns)
        details = [{"name": name, "type": None} for name in columns]
        return self.collection_result(spec, records, details)

    def build_view_query(
        self, spec: DatasetSpec, columns: list[dict[str, str | None]], start: datetime, end: datetime
    ) -> tuple[str, tuple[Any, ...]]:
        """Build a bounded, parameterized SELECT for a view using its described columns."""
        column_names = [column["name"] for column in columns]
        select_list = ", ".join('"' + name.replace('"', '""') + '"' for name in column_names)
        query = f"SELECT {select_list} FROM {spec.source}"
        parameters: tuple[Any, ...] = ()
        if not spec.time_column:
            query += f" LIMIT {self.max_records_per_category}"
            return query, parameters

        time_name = spec.time_column.upper() if spec.time_column.islower() else spec.time_column
        available = {name.casefold() for name in column_names}
        if time_name.casefold() not in available:
            raise ValueError(f"Configured time column {spec.time_column!r} is absent from {spec.source}")
        if spec.category == "focus_cost_usage" and "chargeperiodend" in available:
            query += ' WHERE "ChargePeriodStart" < %s AND "ChargePeriodEnd" > %s'
            query += f' ORDER BY "ChargePeriodStart" DESC LIMIT {self.max_records_per_category}'
            return query, (end, start)

        quoted_time_name = '"' + time_name.replace('"', '""') + '"'
        query += f" WHERE {quoted_time_name} >= %s AND {quoted_time_name} < %s"
        column_type = next((c["type"] for c in columns if c["name"].casefold() == time_name.casefold()), None)
        if column_type and column_type.upper() == "DATE":
            inclusive_day_end = end.date() + (timedelta(days=1) if end.time() != datetime.min.time() else timedelta())
            parameters = (start.date(), inclusive_day_end)
        else:
            parameters = (start, end)
        query += f" ORDER BY {quoted_time_name} DESC LIMIT {self.max_records_per_category}"
        return query, parameters

    def collection_result(
        self, spec: DatasetSpec, records: list[dict[str, Any]], columns: list[dict[str, str | None]]
    ) -> CollectionResult:
        """Summarize fetched rows with status and the earliest and latest record timestamps."""
        timestamps = [
            self.utils.record_timestamp(record, spec.timestamp_column)
            for record in records
        ] if spec.timestamp_column else []
        timestamps = [timestamp for timestamp in timestamps if timestamp]
        return CollectionResult(
            spec=spec,
            status=Status.COLLECTED[0] if records else Status.EMPTY[0],
            records=records,
            earliest_timestamp=min(timestamps) if timestamps else None,
            latest_timestamp=max(timestamps) if timestamps else None,
            columns=columns,
        )

    def describe_view_columns(self, cursor: Any, source: str) -> list[dict[str, str | None]]:
        """Return source column names and types from Snowflake metadata."""
        cursor.execute(f"DESC VIEW {source}")
        columns: list[dict[str, str | None]] = []
        while True:
            batch = cursor.fetchmany(self.batch_size)
            if not batch:
                break
            columns.extend({"name": str(row[0]), "type": str(row[1]) if len(row) > 1 and row[1] is not None else None}
                           for row in batch if row and row[0])
        if not columns:
            raise RuntimeError(f"No columns returned while describing {source}")
        return columns

    def fetch_records(self, cursor: Any, query: str, parameters: tuple[Any, ...]) -> list[dict[str, Any]]:
        """Execute a query and return up to the per-category limit of rows keyed by source column."""
        cursor.execute(query, parameters)
        return self.fetch_current_result(cursor, [description[0] for description in cursor.description])

    def fetch_current_result(self, cursor: Any, columns: list[str]) -> list[dict[str, Any]]:
        """Fetch batches from the cursor's current result up to the per-category limit."""
        records: list[dict[str, Any]] = []
        while True:
            batch = cursor.fetchmany(self.batch_size)
            if not batch:
                return records
            remaining = self.max_records_per_category - len(records)
            records.extend(dict(zip(columns, row)) for row in batch[:remaining])
            if len(records) >= self.max_records_per_category:
                return records

    def account_context(self) -> dict[str, Any]:
        """Read Snowflake session identity used by normalized records and CLI output."""
        cursor = self.connection.cursor()
        try:
            cursor.execute("SELECT CURRENT_ACCOUNT(), CURRENT_ORGANIZATION_NAME(), CURRENT_REGION(), CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE()")
            row = cursor.fetchone()
            return dict(zip(("account", "organization", "region", "user", "role", "warehouse"), row))
        finally:
            cursor.close()

    def execute(self, statement: str) -> None:
        """Execute one session statement and close its cursor."""
        cursor = self.connection.cursor()
        try:
            cursor.execute(statement)
        finally:
            cursor.close()
