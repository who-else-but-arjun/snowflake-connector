import argparse
from datetime import datetime, timezone
from pathlib import Path

from .connector import SnowflakeCostConnector
from .scripts.generate_outputs import generate_outputs


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO timestamp and treat a missing offset as UTC."""
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)


def main() -> None:
    """Run the Snowflake collection CLI."""
    parser = argparse.ArgumentParser(description="Collect Snowflake cost data and generate assessment outputs")
    parser.add_argument("--start", required=True, type=parse_timestamp)
    parser.add_argument("--end", required=True, type=parse_timestamp)
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--max-records-per-category", type=int, default=200)
    arguments = parser.parse_args()
    connector = SnowflakeCostConnector.from_environment(
        max_records_per_category=arguments.max_records_per_category
    )
    try:
        outputs = generate_outputs(connector, arguments.start, arguments.end, Path(arguments.output_dir))
        evidence = outputs["execution_evidence"]
        print(f"Authenticated account={evidence['account_redacted']} region={evidence['region']}")
        print(f"Collected {len(outputs['raw_records'])} rows across {len(outputs['coverage'])} categories (limit {arguments.max_records_per_category} per category)")
        print(f"Wrote coverage, evidence, raw, normalized, and schema outputs to {arguments.output_dir}")
    finally:
        connector.close()


if __name__ == "__main__":
    main()
