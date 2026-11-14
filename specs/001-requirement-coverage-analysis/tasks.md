# Tasks: 要件カバレッジの自動判定

**Input**: `/specs/001-requirement-coverage-analysis/` の spec.md、plan.md、research.md、data-model.md、contracts/、quickstart.md

**Prerequisites**: plan.md、spec.md

**Tests**: 憲章 III に従い、書くテストは「業務ロジックの単体（csv_io、coverage）」と「E2E」のみ。
スクリプトや文書の中身を調べるテストと、チェック用のシェルは作らない。

**Organization**: ユーザーストーリーごとにまとめる。P1 だけで MVP が成り立つ。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 並列にできる（別のファイル、依存なし）
- **[Story]**: 対応するストーリー（US1、US2、US3）

---

## Phase 1: Setup（共通の準備）

**Purpose**: `cdk init` の既定の雛形を、憲章に合わせて整える

- [x] T001 `test/`、`jest.config.js`、jest 関連の依存を削除する（憲章 III）。対象: `test/`、`jest.config.js`、`package.json`
- [x] T002 `lib/infra-stack.ts` を、plan の構成（`storage.ts`、`runner.ts`、`workflow.ts`）に分ける土台に置き換える。対象: `lib/infra-stack.ts`、`bin/infra.ts`
- [x] T003 [P] Python の開発用の依存（pytest、ruff）を、版を固定して追加する。対象: `pyproject.toml`、`pylock.toml`
- [x] T004 [P] Markdown の lint（markdownlint-cli2）を、版を固定して追加し、`pnpm lint` を用意する。対象: `package.json`
- [x] T005 [P] `pnpm lint`（ruff、tsc、markdownlint-cli2）を整える。自前のチェック用シェルは作らない。対象: `package.json`、`pyproject.toml`
- [x] T006 Python の入口（`src/req_coverage_runner/__init__.py` の雛形）を、`handler.py` に置き換える。古い `pnpm runner` のスクリプトも `package.json` から消す。対象: `src/req_coverage_runner/handler.py`、`package.json`

---

## Phase 2: Foundational（すべてのストーリーの前に必要）

**Purpose**: 前提の実機確認と、ストーリーに共通の業務ロジック

**⚠ CRITICAL**: T007〜T008 で前提が崩れたら、plan と research を直してから進める

- [ ] T007 公式の decider（`strands-labs/strands-decider` の `deploy/lambda`）を、固定したコミットでデプロイし、別名 `live` の ARN を控える。SnapStart は切る（research D4）。成果物: 手順を `quickstart.md` に反映
- [ ] T008 decider に、要件1件と100個のテストの質問を直接送り、所要時間、1回の上限、日本語の判定の質を確かめる。decider の別名 `live` の ARN で、直接呼べることも確かめる。結果を `research.md` の「未確認」に記録する。成果物: `research.md`
- [x] T009 [P] 単体テスト（赤）: CSV の検証。ヘッダ違い、空の値、`id` の重複、0件、101件、UTF-8 以外、BOM つき。対象: `tests/unit/test_csv_io.py`
- [x] T010 [P] 単体テスト（赤）: 集計。1件以上の「はい」でカバー済み、0件で未カバー、`score` の降順、しきい値 0.5 の境界。対象: `tests/unit/test_coverage.py`
- [x] T011 [P] `csv_io.py` を実装する（T009 を通す）。対象: `src/req_coverage_runner/csv_io.py`
- [x] T012 [P] `coverage.py` を実装する（T010 を通す）。対象: `src/req_coverage_runner/coverage.py`
- [x] T013 [P] S3 バケット（暗号化、公開しない、EventBridge への通知を有効にする、`cdk destroy` で中身ごと消える設定）を作る。対象: `lib/storage.ts`

**Checkpoint**: 前提が確かめられ、業務ロジックの単体テストが通る

---

## Phase 3: User Story 1 - ファイルを置くだけでカバレッジのレポートが得られる (Priority: P1) 🎯 MVP

**Goal**: 2つの CSV を置くだけで、`output/report.*` が出る

**Independent Test**: サンプルを置き、`report.csv` が 12 × 15 = 180 行で出る

### Tests for User Story 1

- [ ] T014 [US1] E2E テストを書く（赤）: 新しい `run-id` にサンプルを置き、`report.csv` の出現を待ち、行数 180 と、要件の数の一致（SC-003）を確かめる。対象: `tests/e2e/test_run_sample.py`

### Implementation for User Story 1

- [ ] T015 [P] [US1] `decider_client.py` を実装する。要件を state、テストを noul の質問にして呼ぶ。一時的なエラーのみ3回再試行する。読み取りの待ちを 900 秒にする。対象: `src/req_coverage_runner/decider_client.py`
- [ ] T016 [P] [US1] `report.py` を実装する。`report.csv`、`report.json`、`report.md` を、contracts/report.md のとおりに書く。対象: `src/req_coverage_runner/report.py`
- [ ] T017 [US1] `handler.py` を実装する。CSV の読み込み、要件ごとの decider の呼び出し（同時 25 本）、集計、レポートの書き出し。対象: `src/req_coverage_runner/handler.py`
- [ ] T018 [US1] runner の Lambda（Python 3.14、512 MB、上限15分）と IAM（実行フォルダの読み書き、decider の呼び出し）を作る。対象: `lib/runner.ts`
- [ ] T019 [US1] Step Functions を作る: 実行の印の条件つき書き込み、`input/` の一覧で2ファイルを待つ（最大10分）、runner の呼び出し。全体のタイムアウト（30分）を付ける。対象: `lib/workflow.ts`
- [ ] T020 [US1] EventBridge の規則を作る（`input/` 配下の2ファイルの作成で起動）。対象: `lib/workflow.ts`
- [ ] T021 [US1] スタックを組み立て、decider の ARN をコンテキストで受け取る。`pnpm cdk synth` を通す。対象: `lib/infra-stack.ts`、`bin/infra.ts`
- [ ] T022 [US1] デプロイして、T014 の E2E を通す。未確認の項目（条件つき書き込み、15分に収まるか）の結果を `research.md` に記録する

**Checkpoint**: US1 が単独で動き、MVP として使える

---

## Phase 4: User Story 2 - 要件とテストの対応を、確信度つきで確かめられる (Priority: P2)

**Goal**: 判定の妥当性を、人が確かめられる

**Independent Test**: レポートが、要件、テスト、判定、確信度を持ち、未カバーが明示される

- [ ] T023 [US2] E2E テストを書く（赤）: `report.json` の REQ-008、REQ-012 が未カバーであること、全組に `verdict` と `confidence` があることを確かめる。対象: `tests/e2e/test_report_content.py`
- [ ] T024 [US2] `samples/expected.csv` とレポートを比べ、一致の程度（適合率、再現率）を出して記録する（SC-004）。対象: `tests/e2e/test_accuracy.py`
- [ ] T025 [US2] `report.md` の見え方を整える（未カバーを先にまとめる）。必要なら、しきい値や質問の文言を調整し、理由を `research.md` に記録する。対象: `src/req_coverage_runner/report.py`、`src/req_coverage_runner/decider_client.py`

**Checkpoint**: US1 と US2 がどちらも動く

---

## Phase 5: User Story 3 - 課金は判定の間だけで、失敗しても続かない (Priority: P3)

**Goal**: 失敗が分かり、待機中の費用が小さい

**Independent Test**: 不正な入力で `FAILED.json` ができ、実行のあとに課金が続く資源がない

- [ ] T026 [US3] E2E テストを書く（赤）: ヘッダを壊した CSV、`id` が重複した CSV、片方だけの CSV で、期待する `error_code` の `FAILED.json` ができる。対象: `tests/e2e/test_failures.py`
- [ ] T027 [US3] Step Functions に、失敗の経路を作る: エラーの種類に応じた `FAILED.json` の書き込み（`input_timeout`、`inference_failed`、`runner_timeout`）。対象: `lib/workflow.ts`
- [ ] T028 [US3] runner が、検証の失敗を `error_code` つきで返し、decider の失敗（再試行のあと）を `inference_failed` で返すようにする。単体テスト（偽の呼び出しで、再試行と失敗を確かめる）も書く。対象: `src/req_coverage_runner/handler.py`、`tests/unit/test_decider_client.py`
- [ ] T029 [US3] 重複起動の確認: 同じ実行フォルダに再度置いても、新しい実行が始まらず、前回のレポートが変わらない。対象: `tests/e2e/test_failures.py`
- [ ] T030 [US3] 待機中の費用を確かめる: スタックと decider の構成に、常時動く資源がないことを、デプロイ後のリソース一覧で確認し、結果を `research.md` に記録する（SC-006）

**Checkpoint**: すべてのストーリーが動く

---

## Phase 6: Polish

- [ ] T031 [P] README に、デプロイの手順（decider が先、次にスタック）と、実測の所要時間と費用を書く。対象: `README.md`
- [ ] T032 `quickstart.md` の手順を、実際に最初から最後まで実行して確かめる
- [ ] T033 `pnpm lint` を通す。対象: 全体
- [ ] T034 一時ファイルと、検証用にデプロイしたリソースを片付ける（`pnpm cdk destroy`、decider の `cdk destroy`）

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1 → US2 → US3 → Polish
- T007、T008 は、他の作業より先に行う（前提の確認）
- T009〜T013 は、並列にできる。ただし、T011 は T009、T012 は T010 の後
- US1 の中: T015、T016 は並列。T017 は T011、T012、T015、T016 の後。T018〜T021 は T017 の後
- US2、US3 は、US1 のデプロイ（T022）の後

## Implementation Strategy

1. Phase 1〜2 を終える。特に T007、T008 で、decider の所要時間を確かめる
2. US1 だけを完成させ、E2E で確かめる（ここで止めても、MVP になる）
3. US2 で精度を測り、US3 で失敗を整える

## Notes

- 実装の前に、テストが失敗することを確かめる（T009、T010、T014、T023、T026）
- コミットは、利用者が指示したときだけ作る
- 15分の上限に収まらない場合は、Step Functions の Map に移る（research D5）。tasks を直してから進める
