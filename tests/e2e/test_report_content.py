"""US2: 判定と確信度が揃い、未カバーが明示される。"""


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
