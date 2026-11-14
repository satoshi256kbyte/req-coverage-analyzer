"""入力 CSV の読み込みと検証（contracts/input-csv.md）。"""

import csv
import io
from dataclasses import dataclass

MAX_ROWS = 100
HEADER = ["id", "description"]


class CsvError(Exception):
    """入力の不正。`code` は FAILED.json の error_code に使う。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Row:
    id: str
    description: str


def parse_csv(data: bytes, filename: str) -> list[Row]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise CsvError("invalid_encoding", f"{filename}: UTF-8 として読めません") from e

    try:
        records = [r for r in csv.reader(io.StringIO(text, newline="")) if r]
    except csv.Error as e:
        raise CsvError("invalid_header", f"{filename}: CSV として読めません: {e}") from e

    if not records or [c.strip() for c in records[0]] != HEADER:
        raise CsvError("invalid_header", f"{filename}: ヘッダは `id,description` にしてください")

    rows: list[Row] = []
    seen: set[str] = set()
    for number, record in enumerate(records[1:], start=2):
        if len(record) > len(HEADER):
            raise CsvError("invalid_header", f"{filename}: {number}行目の列が多すぎます")
        cells = [c.strip() for c in record]
        if len(cells) < len(HEADER) or not all(cells):
            raise CsvError("empty_value", f"{filename}: {number}行目に空の値があります")
        row = Row(cells[0], cells[1])
        if row.id in seen:
            raise CsvError("duplicate_id", f"{filename}: id が重複しています: {row.id}")
        seen.add(row.id)
        rows.append(row)

    if not rows:
        raise CsvError("no_rows", f"{filename}: データの行がありません")
    if len(rows) > MAX_ROWS:
        raise CsvError("too_many_rows", f"{filename}: {MAX_ROWS}行を超えています（{len(rows)}行）")
    return rows
