"""US3: 失敗が分かり、重複して起動しない。"""

import json
import time

from e2e_helpers import SAMPLES, get_text, put_input, wait_for_output


def _failed(s3, bucket: str, rid: str) -> dict:
    return json.loads(get_text(s3, bucket, f"runs/{rid}/output/FAILED.json"))


def _output_keys(s3, bucket: str, rid: str) -> set[str]:
    response = s3.list_objects_v2(Bucket=bucket, Prefix=f"runs/{rid}/output/")
    return {o["Key"].rsplit("/", 1)[1] for o in response.get("Contents", [])}


def _sample(name: str) -> bytes:
    return (SAMPLES / name).read_bytes()


def test_ヘッダが違うCSVは失敗として記録される(s3, bucket, run_id):
    put_input(s3, bucket, run_id, "requirements.csv", "ID,説明\nREQ-001,ログインできる\n".encode())
    put_input(s3, bucket, run_id, "e2e-tests.csv", _sample("e2e-tests.csv"))

    assert wait_for_output(s3, bucket, run_id) == "failed"
    failure = _failed(s3, bucket, run_id)
    assert failure["error_code"] == "invalid_header"
    assert "requirements.csv" in failure["message"]
    assert failure["run_id"] == run_id
    assert failure["failed_at"]
    assert _output_keys(s3, bucket, run_id) == {"FAILED.json"}


def test_idが重複したCSVは失敗として記録される(s3, bucket, run_id):
    put_input(s3, bucket, run_id, "requirements.csv", _sample("requirements.csv"))
    put_input(s3, bucket, run_id, "e2e-tests.csv", (_sample("e2e-tests.csv").decode() + "E2E-001,again\n").encode())

    assert wait_for_output(s3, bucket, run_id) == "failed"
    failure = _failed(s3, bucket, run_id)
    assert failure["error_code"] == "duplicate_id"
    assert "E2E-001" in failure["message"]
    assert _output_keys(s3, bucket, run_id) == {"FAILED.json"}


def test_片方だけだと10分待って失敗として記録される(s3, bucket, run_id):
    put_input(s3, bucket, run_id, "requirements.csv", _sample("requirements.csv"))

    assert wait_for_output(s3, bucket, run_id, timeout=15 * 60) == "failed"
    assert _failed(s3, bucket, run_id)["error_code"] == "input_timeout"


def test_同じ実行フォルダに再度置いても新しい実行は始まらない(s3, bucket, sample_run):
    key = f"runs/{sample_run.run_id}/output/report.csv"
    before = s3.head_object(Bucket=bucket, Key=key)

    put_input(s3, bucket, sample_run.run_id, "requirements.csv", _sample("requirements.csv"))
    time.sleep(90)

    after = s3.head_object(Bucket=bucket, Key=key)
    assert (after["ETag"], after["LastModified"]) == (before["ETag"], before["LastModified"])
    assert _output_keys(s3, bucket, sample_run.run_id) == {"report.csv", "report.json", "report.md"}
