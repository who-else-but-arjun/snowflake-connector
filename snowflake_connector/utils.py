import json
import hashlib
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from .constants import Status


class Utils:
    @staticmethod
    def present(item: Any) -> bool:
        """Report whether a value contains usable source data."""
        if item is None:
            return False
        if isinstance(item, str):
            return item.strip() != ""
        try:
            return bool(item == item)
        except (TypeError, ValueError):
            return False

    @staticmethod
    def rowKey(category: str, record: dict[str, Any]) -> str:
        """Create a stable identifier for a source row without a source ID."""
        digest = hashlib.sha1(json.dumps(record, sort_keys=True, default=str).encode()).hexdigest()
        return f"{category}:{digest[:16]}"

    @staticmethod
    def utc_now() -> datetime:
        """Return the current UTC timestamp."""
        return datetime.now(timezone.utc)

    @staticmethod
    def as_utc(value: Any) -> datetime | None:
        """Convert a supported date or timestamp value to UTC."""
        if value is None:
            return None
        if isinstance(value, datetime):
            timestamp = value
        elif isinstance(value, date):
            timestamp = datetime.combine(value, datetime.min.time())
        elif isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            try:
                timestamp = datetime.fromisoformat(normalized)
            except ValueError:
                return None
        else:
            return None
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)

    @staticmethod
    def json_value(value: Any) -> Any:
        """Convert supported Snowflake values to JSON-safe values."""
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, (datetime, date)):
            timestamp = Utils.as_utc(value)
            return timestamp.isoformat() if timestamp else value.isoformat()
        if isinstance(value, dict):
            return {str(key): Utils.json_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [Utils.json_value(item) for item in value]
        return value

    @staticmethod
    def record_timestamp(record: dict[str, Any], name: str) -> datetime | None:
        """Read one explicitly named timestamp field and convert it to UTC."""
        return Utils.as_utc(record.get(name))

    @staticmethod
    def classify_error(error: Exception) -> str:
        """Classify Snowflake failures by SQLSTATE without parsing message text."""
        sqlstate = getattr(error, "sqlstate", None)
        sqlstate = sqlstate.upper() if isinstance(sqlstate, str) else None
        if sqlstate == "42501":
            return Status.PERMISSION_DENIED[0]
        if sqlstate == "0A000":
            return Status.UNSUPPORTED[0]
        raw_message = getattr(error, "raw_msg", "")
        if getattr(error, "errno", None) == -20000 and "ACCOUNT_ROOT_BUDGET_NOT_ACTIVATED" in raw_message:
            return Status.UNAVAILABLE_IN_ACCOUNT[0]
        if sqlstate == "42704":
            return Status.UNAVAILABLE_IN_ACCOUNT[0]
        return Status.FAILED[0]

    @staticmethod
    def safe_error(error: Exception) -> str:
        """Describe a database error without copying SQL or source row content."""
        code = getattr(error, "errno", None)
        state = getattr(error, "sqlstate", None)
        details = []
        if code is not None:
            details.append(f"Snowflake error {code}")
        if state:
            details.append(f"SQLSTATE {state}")
        message = getattr(error, "raw_msg", None)
        if message:
            details.append(str(message).replace("\r", " ").replace("\n", " "))
        if details:
            return "; ".join(details)
        return type(error).__name__


class OutputWriter:
    """Write JSON and text output files."""

    def write_json(self, path: Path, payload: Any) -> None:
        """Write JSON with exact decimal strings and UTC timestamps."""
        path.write_text(json.dumps(Utils.json_value(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def write_text(self, path: Path, payload: str) -> None:
        """Write UTF-8 text."""
        path.write_text(payload, encoding="utf-8")
