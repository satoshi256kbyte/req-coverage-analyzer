# 契約: 入力 CSV

## 共通

| 項目 | 規則 |
| --- | --- |
| 文字コード | UTF-8（BOM なしを推奨。BOM があっても読む） |
| ヘッダ行 | 必須。`id,description` |
| 区切り | カンマ。`"` で囲めば、セルの中の改行とカンマを含められる |
| 行数 | 1〜100行（ヘッダを除く） |
| `id` | 空でない。ファイルの中で一意 |
| `description` | 空でない |

## ファイル名

実行フォルダの `input/` に、次の名前で置く。

| ファイル | 内容 |
| --- | --- |
| `requirements.csv` | 要件 |
| `e2e-tests.csv` | E2Eテスト |

## 不正な入力

実行は失敗し、`FAILED.json` に原因を書く（[s3-layout.md](s3-layout.md)）。

| 状況 | `error_code` |
| --- | --- |
| ヘッダが違う | `invalid_header` |
| 空の `id` または `description` | `empty_value` |
| `id` の重複 | `duplicate_id` |
| 0件 | `no_rows` |
| 101件以上 | `too_many_rows` |
| UTF-8 として読めない | `invalid_encoding` |

サンプルは [samples/](../samples/) を参照する。
