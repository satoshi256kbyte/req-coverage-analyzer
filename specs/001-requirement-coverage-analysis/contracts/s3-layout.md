# 契約: S3 の配置

バケットは1つ。キーは次のとおり。`<run-id>` は利用者が決める（`[A-Za-z0-9._-]{1,64}`）。

```text
runs/<run-id>/
├── input/
│   ├── requirements.csv        # 利用者が置く
│   └── e2e-tests.csv           # 利用者が置く
├── state/
│   └── claimed                 # 実行の印（システムが置く。重複起動を除く）
└── output/
    ├── report.csv              # 成功のとき
    ├── report.json             # 成功のとき
    ├── report.md               # 成功のとき
    └── FAILED.json             # 失敗のとき
```

## 規則

- `output/` には、`report.*` と `FAILED.json` のどちらか一方だけが置かれる。
- `runs/` の下は、作成から30日で消える。
- キーは `runs/<run-id>/<フォルダ>/<ファイル名>` の4階層だけを受け付ける。それより深いキーは、無視する。
- 実行のフォルダは使い捨てとする。再実行は、新しい `<run-id>` で行う。
  同じフォルダに再度置いても、新しい実行は始まらない。
- 起動のきっかけは、`input/requirements.csv` または `input/e2e-tests.csv` の作成である。
- 2つが揃うのを、最大10分待つ。揃わなければ、失敗とする（`error_code`: `input_timeout`）。

## FAILED.json

```json
{
  "run_id": "2026-11-14-001",
  "error_code": "duplicate_id",
  "message": "e2e-tests.csv: id が重複しています: E2E-003",
  "failed_at": "2026-11-14T03:00:00Z"
}
```

`error_code` は、[input-csv.md](input-csv.md) の値に加えて、次を使う。

| 値 | 意味 |
| --- | --- |
| `input_timeout` | 2つの CSV が10分以内に揃わなかった |
| `inference_failed` | 判定モデルの呼び出しが、再試行しても失敗した。`message` には、内部の情報（ARN など）を含めず、要件の `id` だけを書く。詳細は runner のログにある |
| `runner_timeout` | 判定の処理が上限の時間を超えた |
| `internal_error` | 想定外のエラー（ログで確認する） |
