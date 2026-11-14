"""US2: 判定と確信度が揃い、未カバーが明示される。"""

from e2e_helpers import sample_rows


def test_すべての組に判定と確信度がある(sample_run):
    for row in sample_run.csv_rows:
        assert row["verdict"] in {"yes", "no"}
        assert 0.0 <= float(row["score"]) <= 1.0
        assert 0.5 <= float(row["confidence"]) <= 1.0
        # 判定は、score のしきい値（0.5）と合っている
        assert (float(row["score"]) >= 0.5) == (row["verdict"] == "yes")


def test_対応するテストがない要件は未カバーと明示される(sample_run):
    # samples/expected.csv で、どのテストにも対応しない要件
    uncovered = {r["id"] for r in sample_run.json["requirements"] if not r["covered"]}
    assert {"REQ-008", "REQ-012"} <= uncovered
    for req_id in ("REQ-008", "REQ-012"):
        assert f"- {req_id}:" in sample_run.markdown.split("## 要件ごとの結果")[0]


def test_対応するテストに確信度がつく(sample_run):
    for req in sample_run.json["requirements"]:
        assert req["covered"] == (req["matched_count"] > 0) == bool(req["matched"])
        for m in req["matched"]:
            assert m["score"] >= 0.5
            assert 0.5 <= m["confidence"] <= 1.0


def test_要件ごとの確度が付き_未カバーは要確認になる(sample_run):
    for req in sample_run.json["requirements"]:
        if req["covered"]:
            # 確度は、一致したテストの最高の確信度
            assert req["confidence"] == max(m["confidence"] for m in req["matched"])
            assert req["level"] in {"high", "medium", "low"}
        else:
            assert req["confidence"] is None
            assert req["level"] == "needs_review"

    table = sample_run.markdown.split("## 要件ごとの結果")[1]
    assert "| 要件 | 説明 | モデルの判定 | 対応テスト数 | 確度 | 確度の札 | 対応するテスト（確信度） |" in table
    lines = [line for line in table.splitlines() if line.startswith("| REQ-")]
    rows = {cells[0]: cells for cells in ([c.strip() for c in line.strip("|").split("|")] for line in lines)}
    # [要件, 説明, モデルの判定, 対応テスト数, 確度, 確度の札, 対応するテスト]。数値の列には、数値だけ。未カバーは空
    for req_id in ("REQ-008", "REQ-012"):
        assert rows[req_id][3] == "0"
        assert rows[req_id][4] == ""
        assert rows[req_id][5] == ""
    assert rows["REQ-009"][2] == "対応あり"
    assert rows["REQ-008"][2] == "対応なし"
    assert float(rows["REQ-009"][4]) >= 0.5
    assert rows["REQ-009"][5] in {"高", "中", "低"}
    # 未カバーの一覧（要確認）に、REQ-008、REQ-012 がある
    assert "## 未カバーの要件（要確認）" in sample_run.markdown


def test_どの要件にも対応しなかったテストの一覧が出る(sample_run):
    matched = {r["test_id"] for r in sample_run.csv_rows if r["verdict"] == "yes"}
    expected = [t.id for t in sample_rows("e2e-tests.csv") if t.id not in matched]

    assert [t["id"] for t in sample_run.json["unmatched_tests"]] == expected
    assert sample_run.json["summary"]["unmatched_tests"] == len(expected)
    assert "E2E-015" in expected  # ログアウトのテストは、どの要件にも対応しない
    section = sample_run.markdown.split("## どの要件にも対応しなかったテスト")[1].split("## 要件ごとの結果")[0]
    for test_id in expected:
        assert f"- {test_id}:" in section
