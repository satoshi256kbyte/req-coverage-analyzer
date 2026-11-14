# Implementation Plan: 要件カバレッジの自動判定

**Branch**: `feature/spec-kit` | **Date**: 2026-11-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-requirement-coverage-analysis/spec.md`

## Summary

S3 の実行フォルダに2つの CSV が揃うと、EventBridge が Step Functions を起動する。
Step Functions は、判定用の Lambda（runner）を呼ぶ。
runner は、CSV を検証し、要件ごとに、公式の Strands Decider の Lambda（decider）へ質問し、結果を S3 に出力する。
失敗したときは、Step Functions が `FAILED.json` を書く。

常時動く計算資源はない。課金は、使った時間だけである。
決定の理由は [research.md](research.md) に書く。

## Technical Context

**Language/Version**: TypeScript（CDK、Node.js 26）、Python 3.14（runner。Lambda の `python3.14`）

**Primary Dependencies**: aws-cdk-lib、boto3（Lambda に同梱）。外部の Python 依存は増やさない

**Storage**: S3（1バケット。入力、結果、実行の印）

**Testing**: pytest（業務ロジックの単体）、E2E（実際の AWS に対する実行）。憲章 III のとおり、これ以外のテストは書かない

**Target Platform**: AWS Lambda（runner: arm64、decider: 公式の arm64 版）

**Project Type**: IaC + サーバーレスの処理

**Performance Goals**: 100×100 件を30分以内（SC-002）。見積もりは 10 分前後（実測は research.md）

**Constraints**: 常時動く計算資源を置かない。各 Lambda と Step Functions に上限の時間を付ける。認証なしの公開 URL を作らない

**Scale/Scope**: 要件100件、テスト100件まで（最大1万組）。同時に走る実行は1つ

## Constitution Check

| 原則 | 判定 | 根拠 |
| --- | --- | --- |
| I 仕様が正 | 合格 | この plan は spec.md から導いた |
| II 薄く保つ | 合格 | 自前のコンテナ、DynamoDB、VPC を使わない。decider は公式の部品を使う |
| III テストの範囲 | 合格 | pytest（業務ロジック）と E2E のみ。`cdk init` が作った CDK のテストは削除する |
| IV 一般的なツール | 合格 | Python は ruff、TypeScript は tsc と `cdk synth`、Markdown は markdownlint-cli2。版は固定する |
| V 課金は判定の間だけ | 合格 | EC2 などを置かない。decider は SnapStart を切る（月 約 $0.25）。Lambda に上限の時間を付ける |
| VI 判定の確認 | 合格 | 判定と確信度を CSV と JSON に残す |
| 技術の制約 | 合格 | S3、EventBridge、Step Functions、Lambda。decider は公式の Lambda 版を、版を固定して使う |

設計後の再確認でも、違反はない。複雑さの追跡は不要である。

## 全体の流れ

```text
S3 runs/<run-id>/input/*.csv
  → EventBridge（Object Created、input/ 配下の2ファイル）
  → Step Functions
      1. run-id を取り出す
      2. 実行の印 state/claimed を条件つきで書く（重複起動を除く）
      3. input/ の一覧を取り、2ファイルが揃うまで待つ（最大10分）
      4. runner を呼ぶ（同期、上限15分）
      5. 失敗なら output/FAILED.json を書く
  runner:
      a. 2つの CSV を読み、検証する
      b. 要件ごとに decider を呼ぶ（同時 50 本）
      c. 集計し、report.csv、report.json、report.md を書く
```

### decider への質問

- `state`: 要件の説明。
- `questions`: テストごとに1つの noul（はい／いいえ）。
  `instructions` は「次のE2Eテストは、この要件を確かめていますか？ テスト: <説明>」とする。
- 1要件あたり約 7,000〜9,000 語になる。decider の1回の上限（24,576 語）に収まる。

### 重複起動の除き方

2つの CSV は、それぞれ別のイベントを出す。両方で Step Functions が起動する。
最初の実行だけが、`runs/<run-id>/state/claimed` を `If-None-Match: *` で書いて続行する。
2つ目以降は書き込みに失敗し、何もせずに終わる。
このため、同じ実行フォルダを再度アップロードしても、新しい実行は始まらない（再実行は新しいフォルダで行う）。

### 失敗の扱い

- 1組でも判定に失敗したら、実行全体を失敗にする（Clarifications）。
- decider の呼び出しは、一時的なエラーに限り、3回まで再試行する。
- runner が上限の時間を超えたら、Step Functions が `runner_timeout` として `FAILED.json` を書く。
- Step Functions 全体にも、30分のタイムアウトを付ける。

## Project Structure

### Documentation (this feature)

```text
specs/001-requirement-coverage-analysis/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── input-csv.md
│   ├── s3-layout.md
│   └── report.md
├── samples/
└── checklists/
```

### Source Code (repository root)

```text
bin/infra.ts                  # CDK のエントリ
lib/
├── infra-stack.ts            # スタック本体（下の部品を組み立てる）
├── storage.ts                # S3 バケット
├── runner.ts                 # runner の Lambda と IAM
└── workflow.ts               # Step Functions、EventBridge
src/req_coverage_runner/
├── handler.py                # Lambda の入口
├── csv_io.py                 # CSV の読み込みと検証
├── decider_client.py         # decider の呼び出しと再試行
├── coverage.py               # 判定結果の集計（業務ロジック）
└── report.py                 # レポートの書き出し
tests/
├── unit/                     # coverage.py、csv_io.py の単体テスト
└── e2e/                      # 実際の AWS に対する実行
```

**Structure Decision**: 憲章と、既存の構成（`bin/`、`lib/`、`src/`）に従う。
`test/`（`cdk init` が作った CDK のテスト）は、憲章 III により削除し、`tests/` に置き換える。

## 主な設計の決定

| 項目 | 決定 |
| --- | --- |
| decider | 公式の `deploy/lambda` を、版（コミット）を固定して、別のスタックとしてデプロイする。モデルは `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`、リビジョンを固定、SnapStart は切る |
| decider の呼び出し | runner が、別名 `live` の ARN を指定して直接呼ぶ。公式のスタックが作る Function URL（IAM 認証つき）は使わない |
| 関数の ARN の渡し方 | CDK のコンテキスト（`deciderFunctionArn`）。スタックの出力から手で渡す。別名 `live` の ARN を使う |
| runner | Python 3.14、512 MB、上限15分、同時 50 本。boto3 の読み取りの待ち時間は 900 秒にする |
| 判定 | 要件を state に、全テストを noul の質問にする。0.5 以上を「はい」とする |
| 出力 | `report.csv`、`report.json`、`report.md` |
| IAM | runner: 実行フォルダの読み書きと decider の呼び出しのみ。Step Functions: runner の呼び出しと、実行フォルダの一覧と書き込み |

## Complexity Tracking

違反はないため、記載しない。

## 未確認のこと（実装の最初に確かめる）

[research.md](research.md) の「未確認」を参照する。
