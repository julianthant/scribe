HEADERS = [
    "message_id",
    "received_time",
    "sender",
    "subject",
    "attachment_name",
    "duration_seconds",
    "transcript",
    "model",
    "processed_at",
]


class SheetFormatError(RuntimeError):
    pass


def message_ids_from_column(values: list) -> set[str]:
    """Read message ids from a Sheets values.get of column A."""
    if not values:
        return set()
    first = values[0][0] if values[0] else None
    if first in (None, ""):
        if len(values) == 1:
            return set()
        raise SheetFormatError("Google Sheet header does not match Scribe columns")
    if str(first) != "message_id":
        raise SheetFormatError("Google Sheet header does not match Scribe columns")
    found: set[str] = set()
    for row in values[1:]:
        if row and row[0] not in (None, ""):
            found.add(str(row[0]))
    return found


def header_matches(row: list | None) -> bool:
    if not row:
        return False
    return [str(cell) if cell is not None else "" for cell in row[: len(HEADERS)]] == HEADERS


def build_row(record: dict[str, object]) -> list[object]:
    return [_cell(record[name]) for name in HEADERS]


def _cell(value: object) -> object:
    if not isinstance(value, str):
        return value
    if value[:1] in {"=", "+", "-", "@"}:
        return "'" + value
    return value
