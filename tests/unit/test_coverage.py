import pytest

from req_coverage_runner.coverage import THRESHOLD, Judgment, build_coverage, judge
from req_coverage_runner.csv_io import Row

REQS = [Row("R1", "要件1"), Row("R2", "要件2"), Row("R3", "要件3")]
TESTS = [Row("T1", "テスト1"), Row("T2", "テスト2")]


def _scores(**by_req: dict[str, float]) -> list[Judgment]:
    return [Judgment(r, t, s) for r, d in by_req.items() for t, s in d.items()]


def test_しきい値は0_5で境界は含む():
    assert THRESHOLD == 0.5
    assert judge(0.5).verdict == "yes"
    assert judge(0.4999).verdict == "no"
    assert judge(1.0).verdict == "yes"
    assert judge(0.0).verdict == "no"


def test_確信度は判定の側の確率():
    assert judge(0.9).confidence == pytest.approx(0.9)
    assert judge(0.1).confidence == pytest.approx(0.9)
    assert judge(0.5).confidence == pytest.approx(0.5)


def test_1件以上のはいでカバー済み():
    js = _scores(R1={"T1": 0.9, "T2": 0.2}, R2={"T1": 0.1, "T2": 0.1}, R3={"T1": 0.3, "T2": 0.8})
    cov = build_coverage(REQS, TESTS, js)
    assert [c.covered for c in cov] == [True, False, True]


def test_一致したテストはscoreの降順():
    js = _scores(R1={"T1": 0.6, "T2": 0.95}, R2={"T1": 0, "T2": 0}, R3={"T1": 0, "T2": 0})
    cov = build_coverage(REQS, TESTS, js)
    assert [m.test_id for m in cov[0].matched] == ["T2", "T1"]
    assert cov[0].matched_count == 2


def test_いいえのテストは一致に含めない():
    js = _scores(R1={"T1": 0.49, "T2": 0.2}, R2={"T1": 0, "T2": 0}, R3={"T1": 0, "T2": 0})
    cov = build_coverage(REQS, TESTS, js)
    assert cov[0].matched == []
    assert cov[0].matched_count == 0


def test_要件の並びは入力の順():
    js = _scores(R3={"T1": 0, "T2": 0}, R1={"T1": 0, "T2": 0}, R2={"T1": 0, "T2": 0})
    assert [c.requirement_id for c in build_coverage(REQS, TESTS, js)] == ["R1", "R2", "R3"]


def test_判定が足りないと失敗する():
    js = _scores(R1={"T1": 0.9}, R2={"T1": 0, "T2": 0}, R3={"T1": 0, "T2": 0})
    with pytest.raises(ValueError, match="R1.*T2"):
        build_coverage(REQS, TESTS, js)


def test_知らないidの判定は失敗する():
    js = _scores(R1={"T1": 0, "T2": 0}, R2={"T1": 0, "T2": 0}, R3={"T1": 0, "T2": 0}, R9={"T1": 0})
    with pytest.raises(ValueError, match="R9"):
        build_coverage(REQS, TESTS, js)


def test_範囲外のscoreは失敗する():
    with pytest.raises(ValueError):
        judge(1.1)
    with pytest.raises(ValueError):
        judge(-0.1)
