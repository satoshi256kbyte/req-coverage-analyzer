"""入力 CSV の読み込みと検証（contracts/input-csv.md）。"""

import csv
import io
import re
from dataclasses import dataclass

MAX_ROWS = 100
# decider の1回の上限（24,576 語）に、100件のテストが収まる長さ。実測で、1文字 約 1.4 語
MAX_DESCRIPTION_CHARS = 120
MAX_FILE_BYTES = 128 * 1024
HEADER = ["id", "description"]
# 先頭は文字か数字。表計算ソフトの数式（= + - @）、Markdown の記号、空白、区切りを含められない
ID_PATTERN = re.compile(r"^\w[\w.\-]{0,63}$")


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
    if len(data) > MAX_FILE_BYTES:
        raise CsvError("file_too_large", f"{filename}: {MAX_FILE_BYTES // 1024} KB を超えています")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise CsvError("invalid_encoding", f"{filename}: UTF-8 として読めません") from e

    # 各レコードの開始行（ファイル上の行番号）を、空行や複数行のセルを数えて記録する
    records: list[tuple[int, list[str]]] = []
    try:
        reader = csv.reader(io.StringIO(text, newline=""))
        previous_end = 0
        for record in reader:
            start, previous_end = previous_end + 1, reader.line_num
            if record:
                records.append((start, record))
    except csv.Error as e:
        raise CsvError("invalid_header", f"{filename}: CSV として読めません: {e}") from e

    if not records or [c.strip() for c in records[0][1]] != HEADER:
        raise CsvError("invalid_header", f"{filename}: ヘッダは `id,description` にしてください")

    rows: list[Row] = []
    seen: set[str] = set()
    for number, record in records[1:]:
        if len(record) > len(HEADER):
            raise CsvError("invalid_header", f"{filename}: {number}行目の列が多すぎます")
        cells = [c.strip() for c in record]
        if len(cells) < len(HEADER) or not all(cells):
            raise CsvError("empty_value", f"{filename}: {number}行目に空の値があります")
        row = Row(cells[0], cells[1])
        if not ID_PATTERN.fullmatch(row.id):
            message = f"{filename}: {number}行目の id は、英数字、`_`、`.`、`-` の64字以内にしてください"
            raise CsvError("invalid_id", message)
        if len(row.description) > MAX_DESCRIPTION_CHARS:
            message = f"{filename}: {number}行目の description が {MAX_DESCRIPTION_CHARS} 文字を超えています"
            raise CsvError("value_too_long", message)
        if row.id in seen:
            raise CsvError("duplicate_id", f"{filename}: id が重複しています: {row.id}")
        seen.add(row.id)
        rows.append(row)

    if not rows:
        raise CsvError("no_rows", f"{filename}: データの行がありません")
    if len(rows) > MAX_ROWS:
        raise CsvError("too_many_rows", f"{filename}: {MAX_ROWS}行を超えています（{len(rows)}行）")
    return rows
