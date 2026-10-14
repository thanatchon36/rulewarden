import csv
import statistics
from pathlib import Path


def _values(path: Path, column: str) -> list[float]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or column not in reader.fieldnames:
            raise KeyError(column)
        out = []
        for row_no, row in enumerate(reader, start=1):
            cell = (row.get(column) or "").strip()
            if not cell:
                continue
            try:
                out.append(float(cell))
            except ValueError:
                raise ValueError(f"row {row_no}: {cell!r} is not a number") from None
    return out


def column_stats(path: str | Path, column: str) -> dict[str, float]:
    """Summary statistics for the numeric, non-empty cells of `column`."""
    values = _values(Path(path), column)
    if not values:
        raise ValueError(f"column {column!r} has no values")
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": float(statistics.median(values)),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }
