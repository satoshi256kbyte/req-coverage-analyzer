"""E2E テストの補助関数。"""

import time
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
