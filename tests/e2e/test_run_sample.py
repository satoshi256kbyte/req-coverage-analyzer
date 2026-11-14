"""US1: 2つの CSV を置くだけで、レポートが出る。"""

from e2e_helpers import sample_rows


def test_全組の判定がそろっている(sample_run):
    requirements = sample_rows("requirements.csv")
    tests = sample_rows("e2e-tests.csv")

    # FR-003: 全組が1行ずつある
    assert len(sample_run.csv_rows) == len(requirements) * len(tests) == 180
    pairs = {(r["requirement_id"], r["test_id"]) for r in sample_run.csv_rows}
    assert pairs == {(q.id, t.id) for q in requirements for t in tests}


def test_要件の数と並びが入力と一致する(sample_run):
    requirements = sample_rows("requirements.csv")
    report = sample_run.json

    # SC-003
    assert report["meta"]["requirement_count"] == len(requirements)
    assert [r["id"] for r in report["requirements"]] == [q.id for q in requirements]
    assert report["summary"]["covered"] + report["summary"]["uncovered"] == len(requirements)


def test_人が読む形式がある(sample_run):
    assert sample_run.markdown.startswith("# 要件カバレッジのレポート")
