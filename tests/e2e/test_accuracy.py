"""US2: 人が付けた正解（samples/expected.csv）と、判定を比べる（SC-004）。

結果は、`pnpm test:e2e -rP` で、標準出力に出る。しきい値は設けず、測定して記録する。
"""

import csv

from e2e_helpers import SAMPLES, sample_rows


def _expected_pairs() -> set[tuple[str, str]]:
    with (SAMPLES / "expected.csv").open(encoding="utf-8", newline="") as f:
        return {(r["requirement_id"], r["test_id"]) for r in csv.DictReader(f)}


def test_正解と比べた一致の程度を測る(sample_run):
    requirements = sample_rows("requirements.csv")
    expected = _expected_pairs()
    actual = {(r["requirement_id"], r["test_id"]) for r in sample_run.csv_rows if r["verdict"] == "yes"}

    tp, fp, fn = len(actual & expected), len(actual - expected), len(expected - actual)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    # SC-004: 「カバーの有無」の一致
    expected_covered = {r for r, _ in expected}
    actual_covered = {r["id"] for r in sample_run.json["requirements"] if r["covered"]}
    agree = sum((req.id in expected_covered) == (req.id in actual_covered) for req in requirements)

    print(f"\n[accuracy] pair: precision={precision:.2f} recall={recall:.2f} f1={f1:.2f} (tp={tp} fp={fp} fn={fn})")
    print(f"[accuracy] coverage: {agree}/{len(requirements)} 件で、カバーの有無が一致")
    print(f"[accuracy] missed: {sorted(expected - actual)}")
    print(f"[accuracy] extra: {sorted(actual - expected)}")
    assert 0 <= agree <= len(requirements)
