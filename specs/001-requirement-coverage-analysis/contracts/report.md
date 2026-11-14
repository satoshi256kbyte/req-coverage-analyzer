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
      "confidence": 0.9312,
      "level": "high",
      "matched_count": 2,
      "matched": [
        { "test_id": "E2E-001", "score": 0.9312, "confidence": 0.9312 }
      ]
    }
  ],
  "unmatched_tests": [{ "id": "E2E-015", "description": "…" }],
  "summary": { "covered": 10, "uncovered": 2, "unmatched_tests": 1 }
}
```

- `requirements` の並びは、入力の順。
- `confidence` は、カバー済みの要件では、`matched` の最高の `confidence`。未カバーの要件では、`null`。
- `level` は、`confidence` が 0.9 以上で `high`、0.7 以上で `medium`、それ未満で `low`。未カバーの要件は、`needs_review`（要確認）。
- `matched` は、`score` の降順。
- `unmatched_tests` は、どの要件でも「はい」と判定されなかったテスト。入力の順。
- 全組の判定は `report.csv` にある。

## report.md（人が読む）

- 先頭に、実行の情報と、カバー済みと未カバーの件数を書く。
- 要件ごとの表の列: `id`、説明、モデルの判定（対応あり、対応なし）、対応テスト数、確度、確度の札（高、中、低）、対応するテスト（確信度つき）。
  - 数値の列（対応テスト数、確度）には、数値だけを書く。未カバーの要件の確度と札は、空にする。
- 未カバーの要件は、「未カバーの要件（要確認）」として、見つけやすいよう、先にまとめて書く。
- 「どの要件にも対応しなかったテスト」も、続けてまとめて書く。要件より、テストが多いのは普通なので、異常とは書かず、見逃しか、要件にない動作のテストかを、確かめる手がかりとして書く。

`report.csv` は、組ごとの判定だけで、要件ごとの確度は含まない。
