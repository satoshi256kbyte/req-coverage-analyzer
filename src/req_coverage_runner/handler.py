"""runner の Lambda の入口。

入力: {"run_id": "<実行フォルダの名前>"}
環境変数: BUCKET_NAME、DECIDER_FUNCTION_ARN、CONCURRENCY（省略時 50）

返す値:
- 成功: {"status": "succeeded", ...}
- 入力の不正や decider の失敗: {"status": "failed", "error_code": ..., "message": ...}
  （FAILED.json は、Step Functions が書く）
- 想定外の例外は、そのまま投げる（Step Functions が受ける）
"""

import os
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from req_coverage_runner.coverage import Judgment, build_coverage
from req_coverage_runner.csv_io import CsvError, Row, parse_csv
from req_coverage_runner.decider_client import DeciderError, Invoker, judge_requirement, make_invoker
from req_coverage_runner.report import RunMeta, render_csv, render_json, render_markdown

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
DEFAULT_CONCURRENCY = 50


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_rows(s3: Any, bucket: str, run_id: str, name: str) -> list[Row]:
    key = f"runs/{run_id}/input/{name}"
    try:
        data = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "NoSuchKey":
            raise CsvError("input_timeout", f"{name}: 入力がありません") from e
        raise
    return parse_csv(data, name)


def _judge_all(invoke: Invoker, requirements: list[Row], tests: list[Row], concurrency: int) -> list[Judgment]:
    """要件ごとに decider を呼ぶ。1件でも失敗したら、残りを取り消して、失敗を投げる。"""
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(judge_requirement, invoke, r, tests) for r in requirements]
        judgments: list[Judgment] = []
        try:
            for future in futures:
                judgments += future.result()
        except BaseException:
            for future in futures:
                future.cancel()
            raise
    return judgments


def run_analysis(
    s3: Any,
    bucket: str,
    run_id: str,
    raw_invoke: Invoker,
    concurrency: int = DEFAULT_CONCURRENCY,
    now: Callable[[], str] = _now,
) -> dict[str, Any]:
    started_at = now()
    try:
        requirements = _read_rows(s3, bucket, run_id, "requirements.csv")
        tests = _read_rows(s3, bucket, run_id, "e2e-tests.csv")

        models: set[str] = set()

        def invoke(payload: dict[str, Any]) -> dict[str, Any]:
            body = raw_invoke(payload)
            if isinstance(body.get("model"), str):
                models.add(body["model"])
            return body

        judgments = _judge_all(invoke, requirements, tests, concurrency)
    except CsvError as e:
        return {"status": "failed", "error_code": e.code, "message": e.message}
    except DeciderError as e:
        return {"status": "failed", "error_code": "inference_failed", "message": str(e)}

    coverage = build_coverage(requirements, tests, judgments)
    meta = RunMeta(run_id, ", ".join(sorted(models)) or "unknown", started_at, now())
    outputs = {
        "report.md": ("text/markdown", render_markdown(meta, requirements, tests, coverage)),
        "report.csv": ("text/csv", render_csv(requirements, tests, judgments)),
        "report.json": ("application/json", render_json(meta, requirements, tests, coverage)),
    }
    for name, (content_type, text) in outputs.items():
        s3.put_object(
            Bucket=bucket,
            Key=f"runs/{run_id}/output/{name}",
            Body=text.encode("utf-8"),
            ContentType=f"{content_type}; charset=utf-8",
        )
    covered = sum(c.covered for c in coverage)
    return {"status": "succeeded", "run_id": run_id, "covered": covered, "uncovered": len(coverage) - covered}


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    run_id = event["run_id"]
    if not isinstance(run_id, str) or not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError(f"run_id が不正です: {run_id!r}")
    return run_analysis(
        s3=boto3.client("s3"),
        bucket=os.environ["BUCKET_NAME"],
        run_id=run_id,
        raw_invoke=make_invoker(os.environ["DECIDER_FUNCTION_ARN"]),
        concurrency=int(os.environ.get("CONCURRENCY", DEFAULT_CONCURRENCY)),
    )
