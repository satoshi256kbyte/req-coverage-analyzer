# req-coverage-analyzer

要件定義とE2Eテスト一覧（CSV）を突き合わせ、AIを用いて「どの要件がどのE2Eテストでカバーされているか」を自動判定し、レポートにするシステム。

検証用途（PoC）のMVPとして、実用性とコスト効率を最速で確かめる。

## 開発の進め方

[GitHub Spec Kit](https://github.com/github/spec-kit) による仕様駆動開発。
実装の前に、仕様（`specs/`）と憲章（`.specify/memory/constitution.md`）を定め、それを正として進める。

## 技術スタック

| 分類 | 内容 |
| --- | --- |
| AIモデル | Strands Decider 2B（AWS Strands Labs。分類と判断に特化した小さなモデル） |
| 実行環境 | AWS Lambda（公式の Lambda 版、CPU の arm64） |
| オーケストレーション | AWS Step Functions、Amazon EventBridge |
| ストレージ | Amazon S3 |
| IaC | AWS CDK（TypeScript） |
| パッケージ管理 | pnpm 12（Node.js と Python を一括）、ツールの版は mise で固定 |

## 処理の流れ

常時動く計算資源はなく、使った時間だけ課金される。

```mermaid
flowchart TD
    U["利用者"] -->|"CSV を2つ置く"| IN["S3<br/>runs/run-id/input/"]
    IN -->|"ファイル作成"| EB["EventBridge"]
    EB --> SF["Step Functions"]
    SF -->|"2つ揃うまで待つ"| SF
    SF -->|"呼ぶ"| RN["Lambda: runner<br/>CSV の検証と集計"]
    RN -->|"要件ごとに質問<br/>(同時 25 本)"| DC["Lambda: decider<br/>Strands Decider 2B"]
    DC -->|"はい／いいえ と確信度"| RN
    RN -->|"成功"| OUT["S3<br/>runs/run-id/output/<br/>report.csv / json / md"]
    RN -.->|"失敗"| SF
    SF -.->|"失敗を記録"| FAIL["S3<br/>output/FAILED.json"]
```

| 段階 | 内容 |
| --- | --- |
| 入力 | 要件とE2Eテストの CSV を、実行フォルダに置く |
| 起動 | EventBridge が検知し、Step Functions が始まる。2つ揃うまで最大10分待つ |
| 判定 | runner が、要件1件ごとに、全テストについて「確かめているか」を decider に尋ねる |
| 出力 | 成功なら `report.*`、失敗なら `FAILED.json` を置く |

## 構成

| 場所 | 内容 |
| --- | --- |
| `bin/`, `lib/` | AWS CDK（TypeScript） |
| `src/` | 判定用の Lambda（Python） |
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

## タスク

```sh
pnpm build      # CDK の型の検査
pnpm cdk synth -c deciderFunctionArn=<decider の別名 live の ARN>  # テンプレートの生成
pnpm lint       # ruff、tsc、markdownlint-cli2
pnpm test       # 単体テスト（業務ロジック）
pnpm test:e2e   # E2E（デプロイ済みのスタックが必要。環境変数 E2E_BUCKET にバケット名を渡す）
```

デプロイの手順は、[quickstart](specs/001-requirement-coverage-analysis/quickstart.md) を参照する。
