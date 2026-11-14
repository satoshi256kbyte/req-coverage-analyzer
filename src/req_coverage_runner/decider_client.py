"""decider（公式の Strands Decider の Lambda）の呼び出し。"""

import json
import time
from collections.abc import Callable
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, ConnectionError, EndpointConnectionError

from req_coverage_runner.coverage import Judgment
from req_coverage_runner.csv_io import Row

Invoker = Callable[[dict[str, Any]], dict[str, Any]]

QUESTION = "次のE2Eテストは、この要件を確かめていますか？ E2Eテスト: "
STATE_PREFIX = "要件: "

MAX_RETRIES = 3
# 一時的なエラーだけを再試行する。読み取りの待ちの超過は、再試行しない（15分の上限を使い切るため）
RETRYABLE_CODES = {
    "TooManyRequestsException",
    "ServiceException",
    "EC2ThrottledException",
    "ThrottlingException",
    "RequestTimeoutException",
}


class DeciderError(Exception):
    """decider の呼び出しが、再試行しても失敗した。

    文面には、ARN などの内部の情報が入りうる。利用者に見える場所（FAILED.json）には、出さない。
    """

    def __init__(self, message: str, requirement_id: str | None = None) -> None:
        super().__init__(message)
        self.requirement_id = requirement_id


def build_request(requirement: Row, tests: list[Row]) -> dict[str, Any]:
    """要件1件を state に、全テストを noul（はい／いいえ）の質問にする。"""
    return {
        "state": STATE_PREFIX + requirement.description,
        "questions": {t.id: {"type": "noul", "instructions": QUESTION + t.description} for t in tests},
    }


def make_invoker(function_arn: str) -> Invoker:
    # 読み取りの待ちは、冷えた読み込み（約5分）と判定を含めて、900秒にする。再試行は自前で行う
    config = Config(read_timeout=900, connect_timeout=10, retries={"max_attempts": 1})
    client = boto3.client("lambda", config=config)

    def invoke(payload: dict[str, Any]) -> dict[str, Any]:
        response = client.invoke(FunctionName=function_arn, Payload=json.dumps(payload, ensure_ascii=False).encode())
        body = json.loads(response["Payload"].read())
        if response.get("FunctionError"):
            raise DeciderError(f"decider が失敗しました: {str(body)[:300]}")
        return body

    return invoke


def _is_transient(error: Exception) -> bool:
    if isinstance(error, ClientError):
        return error.response.get("Error", {}).get("Code") in RETRYABLE_CODES
    return isinstance(error, ConnectionError | EndpointConnectionError)


def judge_requirement(
    invoke: Invoker,
    requirement: Row,
    tests: list[Row],
    sleep: Callable[[float], None] = time.sleep,
) -> list[Judgment]:
    """要件1件について、全テストの score を得る。一時的なエラーは、3回まで再試行する。"""
    payload = build_request(requirement, tests)
    for attempt in range(MAX_RETRIES + 1):
        try:
            body = invoke(payload)
            break
        except DeciderError as e:
            e.requirement_id = e.requirement_id or requirement.id
            raise
        except Exception as e:
            if not _is_transient(e) or attempt == MAX_RETRIES:
                raise DeciderError(f"{requirement.id}: decider を呼べませんでした: {e}", requirement.id) from e
            sleep(2**attempt)

    answers = body.get("answers")
    if not isinstance(answers, dict):
        raise DeciderError(f"{requirement.id}: decider の答えが読めません: {str(body)[:300]}", requirement.id)
    judgments: list[Judgment] = []
    for test in tests:
        answer = answers.get(test.id)
        if not isinstance(answer, dict) or not isinstance(answer.get("noul"), int | float):
            raise DeciderError(f"{requirement.id} × {test.id}: 答えがありません", requirement.id)
        judgments.append(Judgment(requirement.id, test.id, float(answer["noul"])))
    return judgments
