import pytest

from req_coverage_runner.csv_io import MAX_ROWS, CsvError, Row, parse_csv


def _csv(*lines: str) -> bytes:
    return ("\n".join(lines) + "\n").encode("utf-8")


def test_正しいCSVを読める():
    rows = parse_csv(_csv("id,description", "REQ-001,ログインできる", "REQ-002,打刻できる"), "requirements.csv")
    assert rows == [Row("REQ-001", "ログインできる"), Row("REQ-002", "打刻できる")]


def test_BOMつきでも読める():
    data = "\ufeffid,description\nREQ-001,説明\n".encode()
    assert parse_csv(data, "requirements.csv") == [Row("REQ-001", "説明")]


def test_セルの中のカンマと改行を読める():
    data = _csv("id,description", 'REQ-001,"一行目,カンマあり', '二行目"')
    assert parse_csv(data, "requirements.csv") == [Row("REQ-001", "一行目,カンマあり\n二行目")]


def test_前後の空白は取り除く():
    assert parse_csv(_csv("id,description", "  REQ-001 ,  説明  "), "x.csv") == [Row("REQ-001", "説明")]


@pytest.mark.parametrize("header", ["id", "id,desc", "id,description,extra", "description,id", ""])
def test_ヘッダが違うと失敗する(header):
    with pytest.raises(CsvError) as e:
        parse_csv(_csv(header, "REQ-001,説明"), "requirements.csv")
    assert e.value.code == "invalid_header"
    assert "requirements.csv" in e.value.message


@pytest.mark.parametrize("line", [",説明", "REQ-001,", "REQ-001", " , "])
def test_空の値は失敗する(line):
    with pytest.raises(CsvError) as e:
        parse_csv(_csv("id,description", line), "e2e-tests.csv")
    assert e.value.code == "empty_value"
    assert "e2e-tests.csv" in e.value.message


def test_idの重複は失敗する():
    with pytest.raises(CsvError) as e:
        parse_csv(_csv("id,description", "E2E-001,a", "E2E-002,b", "E2E-001,c"), "e2e-tests.csv")
    assert e.value.code == "duplicate_id"
    assert "E2E-001" in e.value.message


def test_0件は失敗する():
    with pytest.raises(CsvError) as e:
        parse_csv(_csv("id,description"), "requirements.csv")
    assert e.value.code == "no_rows"


def test_100件までは読める():
    lines = ["id,description"] + [f"R-{i},説明{i}" for i in range(MAX_ROWS)]
    assert len(parse_csv(_csv(*lines), "requirements.csv")) == MAX_ROWS


def test_101件は失敗する():
    lines = ["id,description"] + [f"R-{i},説明{i}" for i in range(MAX_ROWS + 1)]
    with pytest.raises(CsvError) as e:
        parse_csv(_csv(*lines), "requirements.csv")
    assert e.value.code == "too_many_rows"


def test_UTF8でない入力は失敗する():
    with pytest.raises(CsvError) as e:
        parse_csv("id,description\nREQ-001,説明\n".encode("shift_jis"), "requirements.csv")
    assert e.value.code == "invalid_encoding"


def test_空行は無視する():
    assert parse_csv(_csv("id,description", "", "REQ-001,説明", ""), "x.csv") == [Row("REQ-001", "説明")]
