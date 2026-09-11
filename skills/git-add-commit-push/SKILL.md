---
name: git-add-commit-push
description: 意図した変更だけを安全にstage・commit・pushし、必要時はlocal checkpointまたは既存checkpoint chainの公開を行う。scope、機密情報、Git状態、remote状態、outgoing commit provenanceを検証し、問題があれば送信前に停止する。
notion_sync: false
---

# Git Add, Commit, Push

## 契約

このSkillの起動は、会話または承認済みPlanから一意に特定できる対象範囲への `git add`、`git commit`、通常の `git push` の承認を含む。`implementation-loop` から `checkpoint` として明示的に委譲された場合は、local `git add`/`git commit` の承認を含むが、pushは含まない。`publish-checkpoint` として明示的に委譲された場合は、既存checkpoint chainのpushの承認を含むが、新しいcommitは含まない。安全チェックを通過した後は段階ごとの追加承認を求めない。

`implementation-loop` からClose処理として委譲された場合は、親Agentが検証した対象Issue、対象範囲、明示的Close指示を承認根拠として引き継ぐ。Push先の明示がなければ `origin/main` を使い、明示された場合だけその送信先を使う。

承認は対象範囲や権限を拡張しない。対象不明、秘密情報、Git途中状態、remote先行/分岐、outgoing commit provenance不明、force pushが必要、認証・外部送信権限不足などでは停止する。`checkpoint` はremoteへ送信せず、`publish-checkpoint` は親Agentから渡された対象Issueの許可checkpoint chain以外のcommitを作成・送信しない。

Git状態を変更する処理は原則カスタムAgent `git-actions` へ委譲し、利用不能なら同等のGit操作可能Agentへ委譲する。

## Operation

委譲元は、対象pathと次のoperationを明示します。

| operation | 実行範囲 | 主な用途 |
| --- | --- | --- |
| `publish` | 対象変更のstage・commit・push | 通常の公開。operation省略時の既定値 |
| `checkpoint` | 対象変更のstage・commit・commit後確認。pushなし | Human Acceptance candidateまたはhandoff baselineの固定 |
| `publish-checkpoint` | 既存checkpoint chainの確認・remote確認・push。新規commitなし | Human Acceptance PASS後のcandidate公開、またはremote共有が必要なhandoff baseline公開 |

`checkpoint` ではremote確認・pushを行わない。Remote共有が必要なhandoffで先行pushする場合は、理由、送信先remote/ref、target checkpoint SHA、`allowed_checkpoint_shas` を明示した `publish-checkpoint` として委譲する。Close時も同様に、target candidate SHAと送信先remote/refを明示し、Linearへ記録・readback済みの当該Issue checkpoint chainから、今回のtarget refからliveに到達不能なcheckpointだけを古い順に `allowed_checkpoint_shas` として渡す。別remote/refへpush済みという理由だけで許可列から除外しない。

`publish-checkpoint` は次をすべて満たす場合だけ実行する。

- target checkpoint SHAが現在HEADと一致する
- 対象pathに未コミット変更がない
- target remote/refが一意に確定し、push直前までlive stateを確認できる
- `allowed_checkpoint_shas` が親Agentから明示され、Linearへ記録・readback済みの当該Issue checkpointだけから構成される
- `allowed_checkpoint_shas` は今回のtarget refから到達不能なcheckpointだけを古い順に含み、target refから既に到達可能なcheckpointを含まない
- target remote/refからHEADまでのoutgoing commit列が `allowed_checkpoint_shas` と順序を含めて完全一致する
- target remote/refが先行・分岐していない
- force push / rebase / reset等のhistory rewriteを必要としない

`allowed_checkpoint_shas` は「今回のtarget remote/refへ通常pushしたときに、新たにそのtarget refから到達可能になることを許可したcheckpointの順序付き完全列」です。対象Issueで過去に作成した全checkpointの集合でも、どこかのrefへ未pushなcheckpoint集合でもありません。別branch・別remoteへ到達済みでも今回のtarget refから未到達なら含め、今回のtarget refから既に到達可能なら含めません。Linearにpush状態を保存する場合は送信先remote/refと対応づけ、送信先を区別しない `push済み` / `未push` だけを許可列判定の根拠にしません。outgoing列に対象Issue外・由来不明・未承認commitが1件でも含まれる、許可列に不足・余剰・順序不整合がある、またはtarget refごとのreachability / provenanceを確認できない場合はpushせずBLOCKEDとする。

停止時は、実行済み段階、確認事項、推奨対応、再開条件、commit済みかを日本語の項目名で報告する。

## Scope

- ユーザーが明示したpathを最優先する
- Path指定がなければ、現在の会話・承認済みPlan・直前の実装報告から今回の1実装単位の変更pathを一意に特定できる場合だけ推定する
- 複数の実装単位、Repository、候補pathが混在する場合は候補を示して確認を求める
- 「全変更」「すべて」が明示された場合だけRepository全体を対象にする
- 実行前からstage済みの対象外変更、未追跡・削除を勝手に含めたり解除したりしない
- 対象pathに今回Issue以外由来の既存変更が混在していると確認される場合は停止する。Hunk単位で自動分離しない
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

`publish`/`publish-checkpoint` では、この時点でtarget remote/refを確定して取得し、remote先行・分岐、target refからのcheckpoint reachability、outgoing commitを確認する。送信先の明示がなければ `origin/main` を使う。`checkpoint` ではremote確認を行わない。

既定送信先が `origin/main` の例:

```bash
git remote get-url origin
git fetch origin main
git log HEAD..origin/main --oneline
git rev-list --reverse origin/main..HEAD
```

明示送信先では同じ確認を `<remote>/<branch>` に対して行う。

`publish` で送信先が `origin/main` の場合、現在branchが `main` でない、または処理開始前からoutgoing commitがある、またはremote側にcommitがある場合は停止する。これにより今回作成するcommit以外を意図せずpushしない。

`publish-checkpoint` ではtarget refがHEADのancestorであることを確認する。target ref側にHEAD未包含のcommitがある、またはtarget refがHEADのancestorでない場合は停止する。target refがHEADのancestorである場合だけ `git rev-list --reverse <target-ref>..HEAD` をoutgoing commit列として取得し、`allowed_checkpoint_shas` と完全一致することを確認する。対象Issue外・由来不明・未承認commit、許可列の不足・余剰・順序不整合があれば停止する。別remote/refへcheckpointが到達済みでも、今回のtarget refから未到達ならoutgoing列と許可列に含める。

`checkpoint` はpushしないため、detached HEADでない名前付きbranchならこのbranch制約を適用しない。

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

対象外変更、競合marker、意図しない大規模変更が混ざる場合も停止する。`main` であること自体は停止理由にしない。

### 3. Stage

`publish`/`checkpoint` では、明示・推定したscopeだけをstageする。

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

Stage済み差分がscope外、機密、競合、意図しない変更を含む場合はcommitしない。`publish-checkpoint` ではstageせず、対象pathの未コミット変更がないことを確認する。

### 4. Commit

`checkpoint` でstage済み差分が空なら「checkpoint対象の変更なし」として終了する。`publish` でstage済み差分が空なら「送信すべき変更なし」として終了できる。差分がある場合、ユーザー指定messageがあればそのまま使い、なければ今回の目的・変更内容から簡潔なmessageを作る。`publish-checkpoint` はcommitを作成せず、指定されたtarget checkpoint SHAと現在のHEADを照合する。

`--no-verify`、`--no-gpg-sign`、`--amend` は使わない。Commit hookが追加変更した場合は自動amendせず停止する。

Commit作成後、push前に作成済みcommitのscopeを確認する。`checkpoint` はこの確認後に終了し、pushへ進まない。

```bash
git status --short
git show --name-status --stat --oneline HEAD
```

作成されたcommitが対象scopeだけで構成されていることを確認する。Commit hook等によりscope外変更がcommitへ入った場合はpushせずBLOCKEDとする。

### 5. Remote確認とPush

`publish`/`publish-checkpoint` では、送信先が明示されていなければ `origin/main` を使用する。明示された場合だけ指定されたremote/branchを使う。`checkpoint` ではこの段階を実行しない。

Push直前にtarget remote/refをもう一度取得し、送信条件が変化していないことを確認する。`publish-checkpoint` ではtarget refからのreachabilityとoutgoing commit列も再取得し、`allowed_checkpoint_shas` と完全一致することを再確認する。

既定送信先が `origin/main` の例:

```bash
git fetch origin main
git log HEAD..origin/main --oneline
git rev-list --reverse origin/main..HEAD
```

- target remote/refを確認できない → 停止
- Target ref側に新しいcommitがある、またはtarget refがHEADのancestorでない → 停止し、pull/rebase/mergeを自動実行しない
- `publish-checkpoint` でoutgoing列と `allowed_checkpoint_shas` が完全一致しない → 停止し、何もpushしない
- 問題がなければ通常pushする。既定の `origin/main` は `git push origin main`、明示送信先は `git push <remote> HEAD:<branch>` を使う
- Force pushは実行しない

Push後、`git status --short --branch` とtarget ref基準のoutgoing確認で結果を検証する。`publish-checkpoint` はoutgoing列が空になりtarget checkpointがtarget refから到達可能であることも確認する。Push失敗後にresetや履歴書換えは行わない。`checkpoint` はpush後確認を行わず、commit後確認の結果を返す。

## 禁止事項

- `git reset --hard`、`git clean`、無確認checkout等でユーザー変更を破棄しない
- `git config` を変更しない
- Hookをskipしない
- Force pushしない
- 対象外変更をstage/commit/deleteしない
- 対象Issue外・由来不明・未承認のoutgoing commitをpushしない
- Remote先行・分岐時に自動pull/rebase/mergeしない
- 送信先を区別しないglobalな `push済み` / `未push` だけでcheckpointを許可列から除外・追加しない

## 完了報告

成功時は次の項目名で簡潔に報告する。

```text
Operation: <publish | checkpoint | publish-checkpoint>
ステージ対象: <paths | なし>
コミット: <hash> <message>
許可checkpoint列: <allowed_checkpoint_shas | 該当なし>
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
