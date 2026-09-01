---
name: git-add-commit-push
description: 意図した変更だけを安全にstage・commitし、明示がなければorigin/mainへpushする。scope、機密情報、Git状態、remote状態を検証し、問題があれば送信前に停止する。
---

# Git Add, Commit, Push

## 契約

このSkillの起動は、会話または承認済みPlanから一意に特定できる対象範囲への `git add`、`git commit`、通常の `git push` の承認を含む。安全チェックを通過した後は段階ごとの追加承認を求めない。

`implementation-loop` からClose処理として委譲された場合は、親Agentが検証した対象Issue、対象範囲、明示的Close指示を承認根拠として引き継ぐ。push先の明示がなければ `origin/main` を使い、明示された場合だけその送信先を使う。

承認は対象範囲や権限を拡張しない。対象不明、秘密情報、Git途中状態、remote先行/分岐、force pushが必要、認証・外部送信権限不足などでは停止する。

Git状態を変更する処理は原則カスタムAgent `git-actions` へ委譲し、利用不能なら同等のGit操作可能Agentへ委譲する。

停止時は、実行済み段階、確認事項、推奨対応、再開条件、commit済みかを日本語の項目名で報告する。

## Scope

- ユーザーが明示したpathを最優先する
- path指定がなければ、現在の会話・承認済みPlan・直前の実装報告から今回の1実装単位の変更pathを一意に特定できる場合だけ推定する
- 複数の実装単位、Repository、候補pathが混在する場合は候補を示して確認を求める
- 「全変更」「すべて」が明示された場合だけRepository全体を対象にする
- 実行前からstage済みの対象外変更、未追跡・削除を勝手に含めたり解除したりしない
- `git add .` や暗黙の全量 `git add -A` は使わない

## 実行

### 1. 状態確認

Repository rootへ移動し、少なくとも次を確認する。

```bash
git rev-parse --show-toplevel
git status --short --branch
git branch --show-current
git diff --name-status
git diff --cached --name-status
git branch -vv
git remote -v
```

Git Repositoryでない、Detached HEAD、merge/rebase/cherry-pick途中、scope不明、Repository外pathでは停止する。

### 2. 機密・scope確認

次のような機密ファイルは自動コミットしない。

```text
.env
.env.*
credentials.json
secrets.*
*.pem
*.key
*.p12
config/local.*
```

対象外変更、競合marker、意図しない大規模変更が混ざる場合も停止する。`main` / `master` / `develop` であること自体は停止理由にしない。

### 3. Stage

明示・推定したscopeだけをstageする。

```bash
git add -- <paths>
```

全量が明示された場合だけ次を使う。

```bash
git add -A -- :/
```

その後、次を確認する。

```bash
git status --short
git diff --cached --name-status
git diff --cached --stat
git diff --cached --check
```

stage済み差分がscope外、機密、競合、意図しない変更を含む場合はcommitしない。

### 4. Commit

stage済み差分が空なら「送信すべき変更なし」として終了できる。差分がある場合、ユーザー指定messageがあればそのまま使い、なければ今回の目的・変更内容から簡潔なmessageを作る。

`--no-verify`、`--no-gpg-sign`、`--amend` は使わない。commit hookが追加変更した場合は自動amendせず停止する。

### 5. Remote確認とPush

送信先が明示されていなければ `origin/main` を使用する。明示された場合だけ指定されたremote / branchを使う。

デフォルト送信先では次を確認する。

```bash
git remote get-url origin
git fetch origin main
git log origin/main..HEAD --oneline
git log HEAD..origin/main --oneline
```

- `origin` または `origin/main` を確認できない → 停止
- `origin/main` が先行・分岐 → 停止し、pull/rebase/mergeを自動実行しない
- 現在branchが `main` でない場合、送信先の明示がなければ停止する
- 問題がなければ `git push origin main`
- force pushは実行しない

送信先が明示された場合も、同等にremote先行・分岐を確認して通常pushだけを行う。

push後、`git status --short --branch` と `git log origin/main..HEAD --oneline`（明示送信先ならその追跡先）で結果を検証する。push失敗後にresetや履歴書換えは行わない。

## 禁止事項

- `git reset --hard`、`git clean`、無確認checkout等でユーザー変更を破棄しない
- `git config` を変更しない
- Hookをskipしない
- force pushしない
- 対象外変更をstage / commit / deleteしない
- remote先行・分岐時に自動pull / rebase / mergeしない

## 完了報告

成功時は次の項目名で簡潔に報告する。

```text
ステージ対象: <paths>
コミット: <hash> <message>
Push先: <remote/branch>
最終状態: <結果>
未コミット変更: <なし | 残っている変更>
```

途中停止時は次の項目名を使う。

```text
結果: BLOCKED
停止箇所: <段階>
確認事項: <確認できた事実>
推奨対応: <推奨する次の行動>
再開条件: <再開に必要な条件>
コミット済み: <はい | いいえ>
```
