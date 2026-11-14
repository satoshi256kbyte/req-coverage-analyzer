import pytest

from req_coverage_runner.csv_io import (
    MAX_DESCRIPTION_CHARS,
    MAX_FILE_BYTES,
    MAX_ROWS,
    CsvError,
    Row,
    parse_csv,
)


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


@pytest.mark.parametrize(
    "bad_id", ["=1+1", "+cmd", "-1", "@SUM(A1)", "a|b", "a b", "a\u3000b", "<img>", "a`b", "x" * 65, "a/b"]
)
def test_idに使えない文字や長さは失敗する(bad_id):
    with pytest.raises(CsvError) as e:
        parse_csv(_csv("id,description", f'"{bad_id}",説明'), "requirements.csv")
    assert e.value.code == "invalid_id"
    assert "requirements.csv" in e.value.message


@pytest.mark.parametrize("good_id", ["REQ-001", "R_1.2", "機能-001", "a", "x" * 64, "E2E-001"])
def test_idに使える文字(good_id):
    assert parse_csv(_csv("id,description", f"{good_id},説明"), "x.csv") == [Row(good_id, "説明")]


def test_説明の長さの上限():
    assert parse_csv(_csv("id,description", f"R1,{'あ' * MAX_DESCRIPTION_CHARS}"), "x.csv")[0].id == "R1"
    with pytest.raises(CsvError) as e:
        parse_csv(_csv("id,description", f"R1,{'あ' * (MAX_DESCRIPTION_CHARS + 1)}"), "x.csv")
    assert e.value.code == "value_too_long"


def test_ファイルの大きさの上限():
    with pytest.raises(CsvError) as e:
        parse_csv(b"x" * (MAX_FILE_BYTES + 1), "requirements.csv")
    assert e.value.code == "file_too_large"


def test_エラーの行番号は空行と複数行のセルを数えたファイル上の行():
    data = _csv("id,description", "", 'R1,"一行目', '二行目"', "R2,")
    with pytest.raises(CsvError) as e:
        parse_csv(data, "requirements.csv")
    assert e.value.code == "empty_value"
    # ヘッダ(1行目)、空行(2行目)、R1 は 3〜4 行目、R2 は 5 行目
    assert "5行目" in e.value.message
