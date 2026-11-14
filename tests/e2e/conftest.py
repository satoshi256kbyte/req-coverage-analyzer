"""E2E テストの共通部品。デプロイ済みのスタックに対して、実際の S3 と Step Functions を使う。

必要な環境変数:
- E2E_BUCKET: スタックの出力 `BucketName`
- E2E_STATE_MACHINE_ARN: スタックの出力 `StateMachineArn`（重複起動のテストで使う）
- E2E_REGION: 省略すると ap-northeast-1
"""

import csv
import io
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import boto3
import pytest
from e2e_helpers import delete_run, get_text, new_run_id, put_samples, wait_for_output


@pytest.fixture(scope="session")
def bucket() -> str:
    name = os.environ.get("E2E_BUCKET")
    if not name:
        pytest.fail("E2E_BUCKET が未設定です。スタックの出力 BucketName を指定してください")
    return name


@pytest.fixture(scope="session")
def s3():
    return boto3.client("s3", region_name=os.environ.get("E2E_REGION", "ap-northeast-1"))


@pytest.fixture(scope="session")
def sfn():
    return boto3.client("stepfunctions", region_name=os.environ.get("E2E_REGION", "ap-northeast-1"))


@pytest.fixture(scope="session")
def state_machine_arn() -> str:
    arn = os.environ.get("E2E_STATE_MACHINE_ARN")
    if not arn:
        pytest.fail("E2E_STATE_MACHINE_ARN が未設定です。スタックの出力 StateMachineArn を指定してください")
    return arn


@pytest.fixture
def run_id(s3, bucket: str) -> Iterator[str]:
    """新しい実行フォルダの名前。テストのあと、フォルダの中身を消す。"""
    rid = new_run_id()
    yield rid
    delete_run(s3, bucket, rid)


@dataclass(frozen=True)
class SampleRun:
    run_id: str
    csv_rows: list[dict[str, str]]
    json: dict[str, Any]
    markdown: str


@pytest.fixture(scope="session")
def sample_run(s3, bucket: str) -> Iterator[SampleRun]:
    """サンプルを置いて、1回だけ実行し、結果を読む。複数のテストで使い回す（費用を抑える）。"""
    rid = new_run_id()
    try:
        put_samples(s3, bucket, rid)
        if wait_for_output(s3, bucket, rid) == "failed":
            raise AssertionError(f"実行が失敗しました: {get_text(s3, bucket, f'runs/{rid}/output/FAILED.json')}")
        out = f"runs/{rid}/output/"
        yield SampleRun(
            run_id=rid,
            csv_rows=list(csv.DictReader(io.StringIO(get_text(s3, bucket, out + "report.csv")))),
            json=json.loads(get_text(s3, bucket, out + "report.json")),
            markdown=get_text(s3, bucket, out + "report.md"),
        )
    finally:
        delete_run(s3, bucket, rid)
