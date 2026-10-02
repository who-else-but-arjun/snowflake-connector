from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class DatasetSpec:
    category: str
    purpose: str
    source: str
    time_column: str | None
    timestamp_column: str | None
    capability: str = "SNOWFLAKE.USAGE_VIEWER database role on the SNOWFLAKE shared database"


@dataclass
class CollectionResult:
    spec: DatasetSpec
    status: str
    records: list[dict[str, Any]]
    error: str | None = None
    earliest_timestamp: datetime | None = None
    latest_timestamp: datetime | None = None
    columns: list[dict[str, str | None]] | None = None


@dataclass(frozen=True)
class ConnectorConfig:
    account: str
    user: str
    password: str | None
    warehouse: str | None
    database: str | None
    schema: str | None
    role: str | None
    authenticator: str | None