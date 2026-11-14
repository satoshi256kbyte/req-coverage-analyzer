# 契約: レポート

3つの形式で、同じ内容を出す。

## report.csv（判定の全組）

| 列 | 内容 |
| --- | --- |
| `requirement_id` | 要件の `id` |
| `test_id` | テストの `id` |
| `verdict` | `yes` または `no` |
| `confidence` | 0.5〜1（小数点以下4桁） |
| `score` | 0〜1（小数点以下4桁） |

行数は、要件の数 × テストの数。並びは、要件、テストの入力順。

## report.json

```json
{
  "meta": {
    "run_id": "2026-11-14-001",
    "model": "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610@<revision>",
    "threshold": 0.5,
    "started_at": "2026-11-14T03:00:00Z",
    "finished_at": "2026-11-14T03:04:00Z",
    "requirement_count": 12,
    "test_count": 15
  },
  "requirements": [
    {
      "id": "REQ-001",
      "description": "…",
      "covered": true,
      "matched_count": 2,
      "matched": [
        { "test_id": "E2E-001", "score": 0.9312, "confidence": 0.9312 }
      ]
    }
  ],
  "summary": { "covered": 10, "uncovered": 2 }
}
```

- `requirements` の並びは、入力の順。
- `matched` は、`score` の降順。
- 全組の判定は `report.csv` にある。

## report.md（人が読む）

- 先頭に、実行の情報と、カバー済みと未カバーの件数を書く。
- 要件ごとの表: `id`、説明、カバーの有無、対応するテスト（確信度つき）。
- 未カバーの要件は、見つけやすいよう、先にまとめて書く。
