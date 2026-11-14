# Quickstart: 動作の確かめ方

実装後に、この手順で端から端まで確かめる。コマンドの詳細は、実装の時点で README に移す。

## 前提

- AWS の認証が済んでいる（`aws sso login` など）
- `mise install` と `pnpm install` が済んでいる
- CDK のブートストラップが、対象のアカウントとリージョンで済んでいる

## 手順

1. 公式の decider をデプロイする（初回のみ。約10分）。

   - 公式のリポジトリ `strands-labs/strands-decider` を、固定したコミットで取得する。
   - `deploy/lambda` で、`npm install` と `npx cdk deploy` を行う。SnapStart は切ったままにする。
   - スタックの出力から、別名 `live` の ARN を控える。

2. 私たちのスタックをデプロイする。

   ```sh
   pnpm cdk deploy -c deciderFunctionArn=<控えた ARN>
   ```

3. サンプルの2つの CSV を、新しい実行フォルダの `input/` に置く。

   - 置き先: `s3://<bucket>/runs/<run-id>/input/`
   - 置くファイル: `samples/requirements.csv` と `samples/e2e-tests.csv`
   - 置き方は、AWS CLI の `s3 cp` でも、コンソールでもよい。

4. Step Functions の実行を確かめる（成功まで、数分から十数分）。
5. `runs/<run-id>/output/report.md` を開く。

## 期待する結果

| 確認 | 期待 |
| --- | --- |
| `report.csv` の行数 | 12 × 15 = 180 行（ヘッダを除く） |
| REQ-008、REQ-012 | 未カバー |
| `expected.csv` との比較 | 一致の程度を記録する（SC-004） |
| 実行のあと | 課金が続く資源がない |

## 失敗の確かめ方

- ヘッダを壊した CSV を置く。`output/FAILED.json` ができる。decider は呼ばれない。
- decider の呼び出しの失敗（`inference_failed`）は、デプロイし直さずに確かめるため、単体テスト（`tests/unit/test_decider_client.py`）で確かめる。

## 後片付け

```sh
pnpm cdk destroy
```

decider のスタックも、`deploy/lambda` で `npx cdk destroy` して消す。
