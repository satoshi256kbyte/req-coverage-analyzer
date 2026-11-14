# req-coverage-analyzer

要件とE2Eテスト一覧を突き合わせ、AIで要件カバレッジを判定する検証用MVP。

## 構成

| 場所 | 内容 |
| --- | --- |
| `bin/`, `lib/`, `test/` | AWS CDK（TypeScript） |
| `src/` | EC2上で動く推論スクリプト（Python） |
| `specs/` | GitHub Spec Kitの仕様書（導入後） |

## パッケージ管理

pnpm 12（Python対応はExperimental）でNode.jsとPythonの依存を一括管理する。
ロックファイルは `pnpm-lock.yaml`（Node.js）と `pylock.toml`（Python）。

## セットアップ

```sh
mise install
pnpm install
```

## タスク

```sh
pnpm build    # CDKのビルド
pnpm test     # CDKのテスト
pnpm cdk synth
pnpm runner   # 推論スクリプトの実行
```
