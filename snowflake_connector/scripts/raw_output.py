"""Write collected raw source records."""

from ..utils import OutputWriter


def write_raw_records(output_dir, records) -> None:
    folder = output_dir / "raw"
    folder.mkdir(parents=True, exist_ok=True)
    OutputWriter().write_json(folder / "raw_records.json", records)
