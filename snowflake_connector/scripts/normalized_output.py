"""Write normalized cost and usage records."""

from ..utils import OutputWriter


def write_normalized_records(output_dir, records) -> None:
    folder = output_dir / "normalized"
    folder.mkdir(parents=True, exist_ok=True)
    OutputWriter().write_json(folder / "normalized_records.json", records)
