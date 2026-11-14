from req_coverage_runner.coverage import Coverage, Match
from req_coverage_runner.csv_io import Row
from req_coverage_runner.report import RunMeta, render_markdown

META = RunMeta("r1", "m", "t0", "t1")


def test_利用者の文は_Markdownの記号を文字として出す():
    requirements = [Row("R1", "a|b <img src=x> ![x](http://example.com) `c` d\n改行")]
    tests = [Row("T1", "t")]
    coverage = [Coverage("R1", True, [Match("T1", 0.9, 0.9)])]

    text = render_markdown(META, requirements, tests, coverage)

    assert "a\\|b \\<img src=x\\> \\!\\[x\\](http://example.com) \\`c\\` d 改行" in text
    assert "<img" not in text.replace("\\<img", "")


def _table_rows(text: str) -> list[list[str]]:
    table = text.split("## 要件ごとの結果")[1]
    lines = [line for line in table.splitlines() if line.startswith("|")]
    return [[c.strip() for c in line.strip("|").split("|")] for line in lines[2:]]


def test_数値の列には数値だけを書き_未カバーは空にする():
    requirements = [Row("R1", "a"), Row("R2", "b")]
    tests = [Row("T1", "t")]
    coverage = [Coverage("R1", True, [Match("T1", 0.93, 0.93)]), Coverage("R2", False, [])]

    text = render_markdown(META, requirements, tests, coverage)
    header = text.split("## 要件ごとの結果")[1].splitlines()[2]
    assert header == "| 要件 | 説明 | モデルの判定 | 対応テスト数 | 確度 | 確度の札 | 対応するテスト（確信度） |"

    covered, uncovered = _table_rows(text)
    # [要件, 説明, モデルの判定, 対応テスト数, 確度, 確度の札, 対応するテスト]
    assert covered[2] == "対応あり"
    assert covered[3] == "1"
    assert covered[4] == "0.93"
    assert covered[5] == "高"
    assert uncovered[2] == "対応なし"
    assert uncovered[3] == "0"
    assert uncovered[4] == ""  # 数値の列に、文字を入れない
    assert uncovered[5] == ""
    assert "要確認" not in "".join(uncovered)


def test_どの要件にも対応しなかったテストの一覧が出る():
    requirements = [Row("R1", "a")]
    tests = [Row("T1", "対応する"), Row("T2", "対応しない | <b>x</b>")]
    coverage = [Coverage("R1", True, [Match("T1", 0.9, 0.9)])]

    text = render_markdown(META, requirements, tests, coverage)
    section = text.split("## どの要件にも対応しなかったテスト")[1].split("## 要件ごとの結果")[0]
    assert "- T2: 対応しない \\| \\<b\\>x\\</b\\>" in section
    assert "T1" not in section
    assert "テスト: 2件、うち要件に対応しなかったもの: 1件" in text


def test_対応しなかったテストが0件ならなしと書く():
    coverage = [Coverage("R1", True, [Match("T1", 0.9, 0.9)])]
    text = render_markdown(META, [Row("R1", "a")], [Row("T1", "t")], coverage)
    assert "## どの要件にも対応しなかったテスト\n\nなし" in text


def test_jsonに対応しなかったテストが入る():
    import json

    from req_coverage_runner.report import render_json

    coverage = [Coverage("R1", True, [Match("T1", 0.9, 0.9)])]
    body = json.loads(render_json(META, [Row("R1", "a")], [Row("T1", "x"), Row("T2", "y")], coverage))
    assert body["unmatched_tests"] == [{"id": "T2", "description": "y"}]
    assert body["summary"]["unmatched_tests"] == 1
