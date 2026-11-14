"""US1: 2つの CSV を置くだけで、レポートが出る。"""

import csv
import io
import json

from e2e_helpers import get_text, put_samples, sample_rows, wait_for_output


def test_サンプルを置くとレポートが出る(s3, bucket, run_id):
    requirements = sample_rows("requirements.csv")
    tests = sample_rows("e2e-tests.csv")

    put_samples(s3, bucket, run_id)
    outcome = wait_for_output(s3, bucket, run_id)

    failed_key = f"runs/{run_id}/output/FAILED.json"
    if outcome == "failed":
        raise AssertionError(f"実行が失敗しました: {get_text(s3, bucket, failed_key)}")

    # report.csv: 全組が1行ずつある（FR-003）
    rows = list(csv.DictReader(io.StringIO(get_text(s3, bucket, f"runs/{run_id}/output/report.csv"))))
    assert len(rows) == len(requirements) * len(tests) == 180
    assert {(r["requirement_id"], r["test_id"]) for r in rows} == {(q.id, t.id) for q in requirements for t in tests}
    assert {r["verdict"] for r in rows} <= {"yes", "no"}

    # report.json: 要件の数と並びが、入力と一致する（SC-003）
    report = json.loads(get_text(s3, bucket, f"runs/{run_id}/output/report.json"))
    assert report["meta"]["requirement_count"] == len(requirements)
    assert [r["id"] for r in report["requirements"]] == [q.id for q in requirements]
    assert report["summary"]["covered"] + report["summary"]["uncovered"] == len(requirements)

    # report.md: 人が読む形式がある
    assert get_text(s3, bucket, f"runs/{run_id}/output/report.md").startswith("# 要件カバレッジのレポート")
