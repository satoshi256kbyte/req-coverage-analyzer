import io
import threading
import time

import pytest
from botocore.exceptions import ClientError

from req_coverage_runner.csv_io import MAX_FILE_BYTES, Row
from req_coverage_runner.decider_client import DeciderError
from req_coverage_runner.handler import _judge_all, run_analysis

REQS = "id,description\nR1,要件1\nR2,要件2\n".encode()
TESTS = "id,description\nT1,テスト1\nT2,テスト2\n".encode()


class FakeS3:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.put: dict[str, bytes] = {}

    def get_object(self, Bucket, Key):  # noqa: N803
        if Key not in self.files:
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": ""}}, "GetObject")
        data = self.files[Key]
        return {"Body": io.BytesIO(data), "ContentLength": len(data)}

    def put_object(self, Bucket, Key, Body, ContentType):  # noqa: N803
        self.put[Key] = Body


def _ok(payload):
    return {"model": "m", "answers": {k: {"type": "noul", "noul": 0.9} for k in payload["questions"]}}


def _files():
    return {"runs/r1/input/requirements.csv": REQS, "runs/r1/input/e2e-tests.csv": TESTS}


def test_成功すると3つの出力を書く():
    s3 = FakeS3(_files())
    result = run_analysis(s3, "b", "r1", _ok, concurrency=2)
    assert result == {"status": "succeeded", "run_id": "r1", "covered": 2, "uncovered": 0}
    assert sorted(s3.put) == [f"runs/r1/output/{n}" for n in ("report.csv", "report.json", "report.md")]


def test_入力の不正は失敗の値を返し何も書かない():
    files = _files()
    files["runs/r1/input/e2e-tests.csv"] = TESTS + b"T1,again\n"
    s3 = FakeS3(files)
    result = run_analysis(s3, "b", "r1", _ok)
    assert result["status"] == "failed"
    assert result["error_code"] == "duplicate_id"
    assert s3.put == {}


def test_片方の入力がないと_input_timeout():
    s3 = FakeS3({"runs/r1/input/requirements.csv": REQS})
    assert run_analysis(s3, "b", "r1", _ok)["error_code"] == "input_timeout"


def test_大きなファイルは本文を読まずに断る():
    class Big(FakeS3):
        def get_object(self, Bucket, Key):  # noqa: N803
            return {"Body": None, "ContentLength": MAX_FILE_BYTES + 1}

    result = run_analysis(Big({}), "b", "r1", _ok)
    assert result["error_code"] == "file_too_large"


def test_deciderの失敗の文面にARNなど内部の情報を出さない():
    def failing(_):
        raise DeciderError("arn:aws:lambda:ap-northeast-1:123456789012:function:x AccessDenied")

    result = run_analysis(FakeS3(_files()), "b", "r1", failing, concurrency=1)
    assert result["status"] == "failed"
    assert result["error_code"] == "inference_failed"
    assert "arn:" not in result["message"]
    assert "123456789012" not in result["message"]
    assert "R1" in result["message"]


def test_1件が失敗したら_前の呼び出しを待たずに失敗する():
    reqs = [Row(f"R{i}", "x") for i in range(1, 5)]
    tests = [Row("T1", "y")]
    release = threading.Event()
    started: list[str] = []

    def invoke(payload):
        name = payload["state"]
        started.append(name)
        if name == "要件: R2":
            raise DeciderError("boom")
        release.wait(5)  # R1、R3 は、解放されるまで終わらない
        return _ok(payload)

    reqs = [Row(r.id, r.id) for r in reqs]
    timer = threading.Timer(5, release.set)
    timer.start()
    began = time.monotonic()
    try:
        with pytest.raises(DeciderError):
            _judge_all(invoke, reqs, tests, concurrency=2)
        elapsed = time.monotonic() - began
    finally:
        release.set()
        timer.cancel()
    assert elapsed < 3  # R1 の完了（5秒）を待たない
    assert "要件: R4" not in started  # 始まっていない呼び出しは、取り消される
