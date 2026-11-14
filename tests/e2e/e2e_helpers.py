"""E2E テストの補助関数。"""

import time
import uuid
from datetime import datetime
from pathlib import Path

import pytest

from req_coverage_runner.csv_io import Row, parse_csv

SAMPLES = Path(__file__).resolve().parents[2] / "specs" / "001-requirement-coverage-analysis" / "samples"
POLL_SECONDS = 10
TIMEOUT_SECONDS = 25 * 60


def sample_rows(name: str) -> list[Row]:
    return parse_csv((SAMPLES / name).read_bytes(), name)


def put_input(s3, bucket: str, rid: str, name: str, data: bytes) -> None:
    s3.put_object(Bucket=bucket, Key=f"runs/{rid}/input/{name}", Body=data)


def put_samples(s3, bucket: str, rid: str) -> None:
    for name in ("requirements.csv", "e2e-tests.csv"):
        put_input(s3, bucket, rid, name, (SAMPLES / name).read_bytes())


def wait_for_output(s3, bucket: str, rid: str, timeout: int = TIMEOUT_SECONDS) -> str:
    """`output/` に結果が出るまで待ち、`report` か `failed` を返す。"""
    deadline = time.monotonic() + timeout
    prefix = f"runs/{rid}/output/"
    while time.monotonic() < deadline:
        keys = {o["Key"] for o in s3.list_objects_v2(Bucket=bucket, Prefix=prefix).get("Contents", [])}
        if prefix + "FAILED.json" in keys:
            return "failed"
        if prefix + "report.csv" in keys and prefix + "report.json" in keys and prefix + "report.md" in keys:
            return "report"
        time.sleep(POLL_SECONDS)
    pytest.fail(f"{timeout}秒待っても、結果が出ませんでした: {prefix}")


def get_text(s3, bucket: str, key: str) -> str:
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")


def new_run_id() -> str:
    return f"e2e-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


def _list_keys(s3, bucket: str, rid: str) -> list[dict[str, str]]:
    keys: list[dict[str, str]] = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=f"runs/{rid}/"):
        keys += [{"Key": o["Key"]} for o in page.get("Contents", [])]
    return keys


def delete_run(s3, bucket: str, rid: str) -> None:
    """実行フォルダの中身を、すべて消す。動いている実行が遅れて書くものも拾うため、空になるまで確かめる。"""
    for _ in range(3):
        keys = _list_keys(s3, bucket, rid)
        if not keys:
            return
        for i in range(0, len(keys), 1000):
            result = s3.delete_objects(Bucket=bucket, Delete={"Objects": keys[i : i + 1000]})
            if result.get("Errors"):
                raise RuntimeError(f"実行フォルダの削除に失敗しました: {result['Errors'][:3]}")
        time.sleep(10)
    if _list_keys(s3, bucket, rid):
        raise RuntimeError(f"実行フォルダに、削除できないものが残っています: runs/{rid}/")


def wait_for_finished_executions(sfn, state_machine_arn: str, after: datetime, timeout: int = 300) -> list[dict]:
    """`after` より後に始まった実行が、1件以上あり、すべて終わるまで待つ。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        executions = [
            e
            for e in sfn.list_executions(stateMachineArn=state_machine_arn, maxResults=20)["executions"]
            if e["startDate"] > after
        ]
        if executions and all(e["status"] != "RUNNING" for e in executions):
            return executions
        time.sleep(POLL_SECONDS)
    pytest.fail(f"{timeout}秒待っても、実行が見つからないか、終わりませんでした")


def entered_states(sfn, execution_arn: str) -> set[str]:
    """実行が通った状態の名前。"""
    names: set[str] = set()
    for page in sfn.get_paginator("get_execution_history").paginate(executionArn=execution_arn):
        for event in page["events"]:
            details = event.get("stateEnteredEventDetails")
            if details:
                names.add(details["name"])
    return names
