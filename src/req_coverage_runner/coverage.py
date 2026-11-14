"""判定結果の集計（data-model.md）。業務ロジック。"""

from dataclasses import dataclass
from typing import Literal

from req_coverage_runner.csv_io import Row

THRESHOLD = 0.5

Verdict = Literal["yes", "no"]


@dataclass(frozen=True)
class Judgment:
    requirement_id: str
    test_id: str
    score: float


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    confidence: float


@dataclass(frozen=True)
class Match:
    test_id: str
    score: float
    confidence: float


@dataclass(frozen=True)
class Coverage:
    requirement_id: str
    covered: bool
    matched: list[Match]

    @property
    def matched_count(self) -> int:
        return len(self.matched)


def judge(score: float) -> Decision:
    if not 0.0 <= score <= 1.0:
        raise ValueError(f"score は 0〜1 にしてください: {score}")
    verdict: Verdict = "yes" if score >= THRESHOLD else "no"
    return Decision(verdict, max(score, 1.0 - score))


def build_coverage(requirements: list[Row], tests: list[Row], judgments: list[Judgment]) -> list[Coverage]:
    req_ids = {r.id for r in requirements}
    test_ids = {t.id for t in tests}
    by_pair: dict[tuple[str, str], float] = {}
    for j in judgments:
        if j.requirement_id not in req_ids:
            raise ValueError(f"知らない要件の判定です: {j.requirement_id}")
        if j.test_id not in test_ids:
            raise ValueError(f"知らないテストの判定です: {j.test_id}")
        by_pair[(j.requirement_id, j.test_id)] = j.score

    result: list[Coverage] = []
    for req in requirements:
        matched: list[Match] = []
        for test in tests:
            score = by_pair.get((req.id, test.id))
            if score is None:
                raise ValueError(f"判定が足りません: {req.id} × {test.id}")
            decision = judge(score)
            if decision.verdict == "yes":
                matched.append(Match(test.id, score, decision.confidence))
        matched.sort(key=lambda m: m.score, reverse=True)
        result.append(Coverage(req.id, bool(matched), matched))
    return result
