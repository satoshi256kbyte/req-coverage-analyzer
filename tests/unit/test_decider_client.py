import pytest
from botocore.exceptions import ClientError

from req_coverage_runner.csv_io import Row
from req_coverage_runner.decider_client import MAX_RETRIES, QUESTION, DeciderError, build_request, judge_requirement

REQ = Row("R1", "ログインできる")
TESTS = [Row("T1", "ログインする"), Row("T2", "ログアウトする")]


def _answers(**scores: float) -> dict:
    return {"model": "m", "answers": {k: {"type": "noul", "noul": v} for k, v in scores.items()}}


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "x"}}, "Invoke")


def test_要件をstateに全テストを質問にする():
    request = build_request(REQ, TESTS)
    assert request["state"] == "要件: ログインできる"
    assert list(request["questions"]) == ["T1", "T2"]
    assert request["questions"]["T1"] == {"type": "noul", "instructions": QUESTION + "ログインする"}


def test_答えを判定にする():
    judgments = judge_requirement(lambda _: _answers(T1=0.9, T2=0.1), REQ, TESTS)
    assert [(j.requirement_id, j.test_id, j.score) for j in judgments] == [("R1", "T1", 0.9), ("R1", "T2", 0.1)]


def test_一時的なエラーは再試行して成功する():
    calls = []
    sleeps: list[float] = []

    def invoke(_):
        calls.append(1)
        if len(calls) < 3:
            raise _client_error("TooManyRequestsException")
        return _answers(T1=0.9, T2=0.1)

    assert len(judge_requirement(invoke, REQ, TESTS, sleep=sleeps.append)) == 2
    assert len(calls) == 3
    assert sleeps == [1, 2]


def test_再試行しても失敗したら失敗する():
    calls = []
    sleeps: list[float] = []

    def invoke(_):
        calls.append(1)
        raise _client_error("ServiceException")

    with pytest.raises(DeciderError, match="R1"):
        judge_requirement(invoke, REQ, TESTS, sleep=sleeps.append)
    assert len(calls) == MAX_RETRIES + 1
    assert sleeps == [1, 2, 4]


def test_一時的でないエラーは再試行しない():
    calls = []

    def invoke(_):
        calls.append(1)
        raise _client_error("AccessDeniedException")

    with pytest.raises(DeciderError):
        judge_requirement(invoke, REQ, TESTS, sleep=lambda _: None)
    assert len(calls) == 1


def test_decider自身の失敗は再試行しない():
    calls = []

    def invoke(_):
        calls.append(1)
        raise DeciderError("decider が失敗しました")

    with pytest.raises(DeciderError):
        judge_requirement(invoke, REQ, TESTS, sleep=lambda _: None)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"answers": "x"},
        _answers(T1=0.9),  # T2 の答えがない
        {"answers": {"T1": {"type": "noul", "noul": 0.9}, "T2": {"type": "noul"}}},
        {"answers": {"T1": {"type": "noul", "noul": 0.9}, "T2": {"type": "noul", "noul": "高い"}}},
    ],
)
def test_答えが欠けている場合は失敗する(body):
    with pytest.raises(DeciderError):
        judge_requirement(lambda _: body, REQ, TESTS)
