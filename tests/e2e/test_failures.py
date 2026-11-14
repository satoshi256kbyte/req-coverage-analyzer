"""US3: 失敗が分かり、重複して起動しない。"""

import json
import time
from datetime import UTC, datetime, timedelta

from e2e_helpers import (
    SAMPLES,
    entered_states,
    get_text,
    put_input,
    wait_for_finished_executions,
    wait_for_output,
)


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


def test_同じ実行フォルダに再度置いても新しい実行は始まらない(s3, bucket, sfn, state_machine_arn, sample_run):
    key = f"runs/{sample_run.run_id}/output/report.csv"
    before = s3.head_object(Bucket=bucket, Key=key)

    after = datetime.now(UTC) - timedelta(seconds=5)
    put_input(s3, bucket, sample_run.run_id, "requirements.csv", _sample("requirements.csv"))

    # 起動された実行は、実行の印で断られて、何もせずに終わる（レポートを作り直す runner まで進まない）
    executions = wait_for_finished_executions(sfn, state_machine_arn, after)
    assert len(executions) == 1
    assert executions[0]["status"] == "SUCCEEDED"
    states = entered_states(sfn, executions[0]["executionArn"])
    assert "AlreadyClaimed" in states
    assert "RunRunner" not in states

    after_head = s3.head_object(Bucket=bucket, Key=key)
    assert (after_head["ETag"], after_head["LastModified"]) == (before["ETag"], before["LastModified"])
    assert _output_keys(s3, bucket, sample_run.run_id) == {"report.csv", "report.json", "report.md"}


def test_別のファイルが先にあっても2つ揃うまで待つ(s3, bucket, run_id):
    """入力の下に別のファイルが2つあっても、揃ったとは見なさない。後から揃えると、実行が成功する。"""
    put_input(s3, bucket, run_id, "notes.txt", b"memo")
    put_input(s3, bucket, run_id, "requirements.csv", _sample("requirements.csv"))
    time.sleep(75)  # 30秒おきの確認を、2回以上通す
    assert _output_keys(s3, bucket, run_id) == set()  # 待たずに、失敗していない

    put_input(s3, bucket, run_id, "e2e-tests.csv", _sample("e2e-tests.csv"))
    assert wait_for_output(s3, bucket, run_id) == "report"


def test_深い階層のキーでは実行が始まらない(s3, bucket, sfn, state_machine_arn, run_id):
    after = datetime.now(UTC) - timedelta(seconds=5)
    s3.put_object(Bucket=bucket, Key=f"runs/{run_id}/deep/input/requirements.csv", Body=_sample("requirements.csv"))

    executions = wait_for_finished_executions(sfn, state_machine_arn, after)
    assert len(executions) == 1
    assert "IgnoredKey" in entered_states(sfn, executions[0]["executionArn"])
    assert not s3.list_objects_v2(Bucket=bucket, Prefix=f"runs/{run_id}/state/").get("Contents")


def test_大きすぎるCSVは失敗として記録される(s3, bucket, run_id):
    put_input(s3, bucket, run_id, "requirements.csv", b"id,description\n" + b"R1," + b"x" * 200_000 + b"\n")
    put_input(s3, bucket, run_id, "e2e-tests.csv", _sample("e2e-tests.csv"))

    assert wait_for_output(s3, bucket, run_id) == "failed"
    assert _failed(s3, bucket, run_id)["error_code"] == "file_too_large"
