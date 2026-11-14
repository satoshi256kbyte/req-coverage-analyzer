# req-coverage-analyzer

要件定義とE2Eテスト一覧（CSV）を突き合わせ、AIを用いて「どの要件がどのE2Eテストでカバーされているか」を自動判定し、レポートにするシステム。

検証用途（PoC）のMVPとして、実用性とコスト効率を最速で確かめる。

## 開発の進め方

[GitHub Spec Kit](https://github.com/github/spec-kit) による仕様駆動開発。
実装の前に、仕様（`specs/`）と憲章（`.specify/memory/constitution.md`）を定め、それを正として進める。

## 技術スタック

| 分類 | 内容 |
| --- | --- |
| AIモデル | Strands Decider 2B（Strands Labs 提供。分類と判断に特化した小さなモデル） |
| 実行環境 | AWS Lambda（Strands Decider 公式の AWS Lambda 版、CPU の arm64） |
| オーケストレーション | AWS Step Functions、Amazon EventBridge |
| ストレージ | Amazon Simple Storage Service（Amazon S3） |
| IaC | AWS Cloud Development Kit（AWS CDK）（TypeScript） |
| パッケージ管理 | pnpm 12（Node.js と Python を一括）、ツールの版は mise で固定 |

## 処理の流れ

利用者は、**要件定義（CSV）とE2Eテスト一覧（CSV）を投入する**だけでよい。
システムが、要件とE2Eテストを突き合わせ、**比較結果（どの要件がどのE2Eテストでカバーされているか）を返す**。

常時動く計算資源はなく、使った時間だけ課金される。

```mermaid
flowchart LR
    U1["利用者"] -->|"① 要件定義（CSV）と<br/>E2Eテスト一覧（CSV）を投入"| IN["Amazon S3<br/>runs/run-id/input/"]
    IN -->|"② ファイルの作成を通知"| EB["Amazon EventBridge"]
    EB -->|"③ 起動"| SF["AWS Step Functions<br/>2つの CSV が揃うまで待つ"]
    SF -->|"④ 呼び出し"| RN["AWS Lambda（runner）<br/>CSV の検証と集計"]
    RN -->|"⑤ 要件ごとに<br/>全テストを質問（同時 50 本）"| DC["AWS Lambda（decider）<br/>Strands Decider 2B"]
    DC -->|"はい／いいえ と確信度"| RN
    RN -->|"⑥ 比較結果を保存"| OUT["Amazon S3<br/>runs/run-id/output/<br/>report.md、report.csv、report.json"]
    OUT -->|"⑦ 比較結果を取得"| U2["利用者"]
    RN -.->|"失敗"| SF
    SF -.->|"失敗を記録"| FAIL["Amazon S3<br/>runs/run-id/output/FAILED.json"]
    FAIL -.->|"失敗を確認"| U2
```

| 段階 | 内容 |
| --- | --- |
| ① 入力 | 要件定義（CSV）とE2Eテスト一覧（CSV）を、Amazon S3 の実行フォルダに置く |
| ②③ 起動 | Amazon EventBridge が検知し、AWS Step Functions が始まる。2つ揃うまで最大10分待つ |
| ④⑤ 判定 | runner が、要件1件ごとに、全テストについて「確かめているか」を decider に尋ねる |
| ⑥⑦ 出力 | 成功なら比較結果（`report.*`）、失敗なら `FAILED.json` を、Amazon S3 に置く。利用者が取得する |

### 比較結果

要件定義とE2Eテスト一覧を突き合わせた結果として、次の内容が得られる。

- 要件ごとに、どのE2Eテストでカバーされているか（確信度つき）。要件ごとの確度（高、中、低）
- カバーされていない要件（人が確かめる）
- どの要件にも対応しなかったE2Eテスト（見逃しか、要件にない動作のテストかを確かめる）

## 構成

| 場所 | 内容 |
| --- | --- |
| `bin/`, `lib/` | AWS CDK（TypeScript） |
| `src/` | 判定用の AWS Lambda 関数（Python） |
| `tests/` | 単体テスト（業務ロジック）と E2E |
| `specs/` | 仕様、設計、サンプル |
| `.specify/` | Spec Kit（憲章、テンプレート） |

## パッケージ管理

pnpm 12（Python 対応は Experimental）で Node.js と Python の依存を一括管理する。
ロックファイルは `pnpm-lock.yaml`（Node.js）と `pylock.toml`（Python）。

## セットアップ

```sh
mise install
pnpm install
```

## デプロイと使い方

東京リージョン（ap-northeast-1）を前提とする。AWS の認証と、AWS CDK のブートストラップが済んでいること。

1. Strands Decider 公式の AWS Lambda 版（decider）を、先にデプロイする（約8分）。手順と固定したコミットは、[quickstart](specs/001-requirement-coverage-analysis/quickstart.md) を参照する。
   出力の `FunctionArn`（別名 `live`）を控える。
2. このスタックをデプロイする（約2分）。

   ```sh
   pnpm cdk deploy -c deciderFunctionArn=<控えた ARN>
   ```

3. 出力の `BucketName` の Amazon S3 バケットに、`runs/<run-id>/input/requirements.csv`（要件定義）と `runs/<run-id>/input/e2e-tests.csv`（E2Eテスト一覧）を置く。
4. `runs/<run-id>/output/` に、比較結果の `report.md`、`report.csv`、`report.json`（失敗なら `FAILED.json`）が出る。
   再実行は、新しい `<run-id>` で行う。形式は [契約](specs/001-requirement-coverage-analysis/contracts/) を参照する。
5. 使い終わったら、`pnpm cdk destroy -c deciderFunctionArn=<ARN>` と、decider 側の `npx cdk destroy` で消す。

### 実測（東京、2026-11-14）

| 項目 | 結果 |
| --- | --- |
| サンプル（要件12件 × テスト15件） | 約 1 分（decider が温まっているとき） |
| 要件100件 × テスト100件（冷えた decider） | 約 4 分 43 秒（30分の目標に収まる） |
| 1回の実行の費用 | 約 $1〜4（冷えた環境が多いほど高い） |
| 待機中の費用 | 月 約 $0.25（decider のコンテナイメージを、Amazon Elastic Container Registry（Amazon ECR）に置く分） |
| 判定の精度（サンプル） | 誤検出 0 件、見つけた割合 64%（詳細は [research](specs/001-requirement-coverage-analysis/research.md)） |

「カバーされている」は信頼できる。「カバーされていない」は、見逃しの可能性があるため、人が確かめる。

### 入力の決まり

- CSV は UTF-8 で、ヘッダは `id,description`。100行まで、128 KB まで。
- `id` は、64字まで。文字、数字、`_`、`.`、`-` だけ。`description` は、120字まで。
- 入力は、信頼できる人が用意したものとする。説明の文に、モデルへの指示を書くと、その行の判定を動かせる。
- 入力とレポートは、30日で消える。

## タスク

```sh
pnpm build      # AWS CDK の型の検査
pnpm cdk synth -c deciderFunctionArn=<decider の別名 live の ARN>  # テンプレートの生成
pnpm lint       # ruff、tsc、markdownlint-cli2
pnpm test       # 単体テスト（業務ロジック）
pnpm test:e2e   # E2E（デプロイ済みのスタックが必要。環境変数 E2E_BUCKET と E2E_STATE_MACHINE_ARN を渡す）
```

デプロイの手順は、[quickstart](specs/001-requirement-coverage-analysis/quickstart.md) を参照する。
