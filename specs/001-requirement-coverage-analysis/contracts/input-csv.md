# 契約: 入力 CSV

## 共通

| 項目 | 規則 |
| --- | --- |
| 文字コード | UTF-8（BOM なしを推奨。BOM があっても読む） |
| ヘッダ行 | 必須。`id,description` |
| 区切り | カンマ。`"` で囲めば、セルの中の改行とカンマを含められる |
| ファイルの大きさ | 128 KB まで |
| 行数 | 1〜100行（ヘッダを除く） |
| `id` | 1〜64字。先頭は文字か数字で、あとは文字、数字、`_`、`.`、`-` だけ（日本語の文字も可）。ファイルの中で一意 |
| `description` | 空でない。120字まで（1回の判定の上限に、100件のテストが収まる長さ） |

`id` の規則は、レポートを表計算ソフトや Markdown で開いたときに、数式や記号として解釈されないようにするためである。

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
| `id` の形が規則に合わない | `invalid_id` |
| `description` が120字を超える | `value_too_long` |
| ファイルが128 KB を超える | `file_too_large` |

サンプルは [samples/](../samples/) を参照する。
