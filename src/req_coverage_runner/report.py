"""レポートの書き出し（contracts/report.md）。"""

import csv
import io
import json
from dataclasses import dataclass

from req_coverage_runner.coverage import THRESHOLD, Coverage, Judgment, judge
from req_coverage_runner.csv_io import Row


@dataclass(frozen=True)
class RunMeta:
    run_id: str
    model: str
    started_at: str
    finished_at: str


def render_csv(requirements: list[Row], tests: list[Row], judgments: list[Judgment]) -> str:
    """全組の判定。並びは、要件、テストの入力順。"""
    by_pair = {(j.requirement_id, j.test_id): j.score for j in judgments}
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["requirement_id", "test_id", "verdict", "confidence", "score"])
    for req in requirements:
        for test in tests:
            score = by_pair[(req.id, test.id)]
            decision = judge(score)
            writer.writerow([req.id, test.id, decision.verdict, f"{decision.confidence:.4f}", f"{score:.4f}"])
    return out.getvalue()


def render_json(meta: RunMeta, requirements: list[Row], tests: list[Row], coverage: list[Coverage]) -> str:
    by_id = {r.id: r for r in requirements}
    covered = sum(c.covered for c in coverage)
    body = {
        "meta": {
            "run_id": meta.run_id,
            "model": meta.model,
            "threshold": THRESHOLD,
            "started_at": meta.started_at,
            "finished_at": meta.finished_at,
            "requirement_count": len(requirements),
            "test_count": len(tests),
        },
        "requirements": [
            {
                "id": c.requirement_id,
                "description": by_id[c.requirement_id].description,
                "covered": c.covered,
                "matched_count": c.matched_count,
                "matched": [
                    {"test_id": m.test_id, "score": round(m.score, 4), "confidence": round(m.confidence, 4)}
                    for m in c.matched
                ],
            }
            for c in coverage
        ],
        "summary": {"covered": covered, "uncovered": len(coverage) - covered},
    }
    return json.dumps(body, ensure_ascii=False, indent=2) + "\n"


_MARKDOWN_SPECIAL = str.maketrans({c: f"\\{c}" for c in "\\|<>[]!`"})


def _cell(text: str) -> str:
    """利用者の文を、Markdown の表や一覧に、そのまま文字として出す。"""
    return text.replace("\r", " ").replace("\n", " ").translate(_MARKDOWN_SPECIAL)


def render_markdown(meta: RunMeta, requirements: list[Row], tests: list[Row], coverage: list[Coverage]) -> str:
    by_id = {r.id: r for r in requirements}
    covered = [c for c in coverage if c.covered]
    uncovered = [c for c in coverage if not c.covered]
    lines = [
        f"# 要件カバレッジのレポート: {meta.run_id}",
        "",
        f"- モデル: {meta.model}",
        f"- 実行: {meta.started_at} 〜 {meta.finished_at}",
        f"- 要件: {len(requirements)}件、E2Eテスト: {len(tests)}件",
        f"- 「はい」のしきい値: {THRESHOLD}",
        f"- カバー済み: {len(covered)}件、未カバー: {len(uncovered)}件",
        "",
        "## 未カバーの要件",
        "",
    ]
    if uncovered:
        lines += [f"- {_cell(c.requirement_id)}: {_cell(by_id[c.requirement_id].description)}" for c in uncovered]
    else:
        lines.append("なし")
    lines += ["", "## 要件ごとの結果", ""]
    lines += ["| 要件 | 説明 | カバー | 対応するテスト（確信度） |", "| --- | --- | --- | --- |"]
    for c in coverage:
        matched = "<br>".join(f"{_cell(m.test_id)}（{m.confidence:.2f}）" for m in c.matched) or "-"
        mark = "○" if c.covered else "×"
        description = _cell(by_id[c.requirement_id].description)
        lines.append(f"| {_cell(c.requirement_id)} | {description} | {mark} | {matched} |")
    return "\n".join(lines) + "\n"
