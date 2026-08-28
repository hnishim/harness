---
name: git-add-commit-push
description: Use when the user asks to stage changes, create a Git commit, and push the current branch in one action. Infer the intended commit scope from the current conversation when paths are omitted, then safely perform git add, git commit, and git push with scope checks, secret detection, protected-branch safeguards, and remote-state validation.
---

# Git Add, Commit, Push

現在のGitリポジトリで、対象をステージングし、コミットし、現在のブランチをリモートへプッシュする一連の処理を1回のスキル実行で行う。各段階が成功した場合だけ次へ進み、失敗した段階以降は実行しない。

## 実行エージェント

Gitの状態を変更する処理は、カスタムエージェント `git-actions` で実行する。

- 別のエージェントからこのスキルを呼び出した場合、Gitの状態変更を始める前に `git-actions` へ委譲する
- `git-actions` を選択できない実行環境では、Git操作を実行可能な代替エージェントを呼び出し、`git add`、`git commit`、`git push` を含む同じ処理を委譲する
- モデル、推論レベル、sandbox設定はカスタムエージェントTOMLで定義する

## 入力とステージング範囲

- ユーザーが明示したファイル・ディレクトリ、または「会話からコミット対象を判定する」の規則で一意に特定できた変更だけを対象にする。パスを受け取ったら `git add -- <paths>` を使う
- ユーザーが「全変更」「すべて」などと明示した場合だけ、リポジトリ全体を対象に `git add -A -- :/` を使う
- 会話から対象を一意に特定できない場合、変更候補を一覧表示して確認を求める。`git add .`、無指定の `git add -A`、暗黙の全量ステージングは行わない
- 実行前から存在するステージ済み変更が対象範囲に含まれると明示されていない場合、その変更をコミットせず停止する。既存のステージ済み変更を勝手に解除・上書きしない
- 対象外の変更、未追跡ファイル、削除ファイルを保持し、ステージング・コミット・削除の対象にしない
- ユーザーが指定したコミットメッセージはそのまま使う。指定がなければ、会話中の今回の目的・Plan・実装報告を優先し、ステージ済み差分と直近のコミット形式を補助情報としてメッセージを生成する

### 会話からコミット対象を判定する

明示的なファイルパスがない場合は、現在の会話から対象範囲を次の順で抽出する。

1. ユーザーが明示したファイル・ディレクトリ、承認済みPlanの対象範囲を最優先する
2. 現在のタスクについて、直前の実装報告や完了報告に記載された変更ファイルを候補にする。作業ツリー上の差分と一致するものだけを採用する
3. ユーザーの「今回の変更」「この変更」「今の変更」などの指示は、直前に会話で完了した1つの実装単位に結び付ける。複数の実装単位や複数リポジトリが候補になる場合は自動採用しない
4. 会話から抽出したパスをリポジトリルートからの相対パスへ正規化し、存在・変更状態・リポジトリ内であることを確認する。ディレクトリ指定は、その配下の変更済みパスだけに展開する
5. 引用された別会話、Skill本文の使用例、参考実装、単なる調査対象や言及だけのパスは、ユーザーが現在の依頼で明示的に対象化しない限り根拠にしない
6. 候補が1つの実装単位にまとまり、対象外の変更を含まず、現在の差分と矛盾しない場合だけ、確認なしで推定対象として扱う。それ以外は候補を示して停止する

推定対象を採用する場合も、ステージング前に対象パス、対象外として保持する変更、推定の根拠を内部で照合する。会話から推定できないことを理由に全変更へ拡張してはならない。

## 実行手順

### 1. リポジトリと状態を確認する

作業ディレクトリを対象リポジトリのルートに移し、すべてのGitコマンドをそのディレクトリで直接実行する。`git -C <path>` は使わない。

読み取り専用の確認を可能な範囲で並列に行う。

```bash
git rev-parse --show-toplevel
git status --short --branch
git branch --show-current
git diff --name-status
git diff --cached --name-status
git log --oneline -5
git branch -vv
git remote -v
```

次の場合はステージング前に停止する。

- Gitリポジトリではない
- Detached HEAD である
- Merge、rebase、cherry-pickの途中である
- 対象ファイルが存在しない、または対象範囲を特定できない
- リポジトリルート外のパスを対象にしようとしている

### 2. 保護対象と機密ファイルを確認する

次のファイルは自動的にコミットしない。

```text
.env
.env.*
.env.local
.env.*.local
credentials.json
secrets.*
*.pem
*.key
*.p12
config/local.*
```

対象差分に該当ファイルがあれば、ファイル名を示して停止する。ユーザーが明示的に指定しても、機密情報を含む可能性を説明し、通常の一括処理には含めない。

現在のブランチが `main`、`master`、`develop` のいずれかであっても、保護ブランチであることだけを理由に確認を求めない。対象範囲、機密ファイル、ステージ済み差分、リモート状態に問題がなければ、そのままコミットとプッシュへ進む。

次の安全チェックに問題がある場合だけ、該当内容を示して停止または確認を求める。

- 対象範囲を一意に特定できない、または対象外の変更が混在している
- 機密ファイル、競合マーカー、意図しない大きな変更が含まれている
- Git操作の途中状態、Detached HEAD、コミットフックによる想定外の変更がある
- アップストリームが先行・分岐している、プッシュ先を一意に決められない、またはForce pushが必要である

上記に該当せず、各段階のコマンドが成功した場合は、段階ごとのユーザー承認を挟まず、`git add`、`git commit`、`git push` を最後まで実行する。

### 3. 対象をステージする

初期状態のステージ済みファイルを記録してから、指定された範囲だけをステージする。

```bash
git add -- <explicit-paths>
```

全量が明示された場合だけ、次を使う。

```bash
git add -A -- :/
```

ステージ後に必ず確認する。

```bash
git status --short
git diff --cached --name-status
git diff --cached --stat
git diff --cached --check
```

ステージ済み差分に対象外ファイル、機密ファイル、競合マーカー、意図しない大きな変更があれば、コミット前に停止する。ステージ済みの内容を確認できない場合も停止する。

### 4. コミットする

ステージ済み差分が空なら停止する。差分と既存のコミット形式に基づき、メッセージには少なくとも以下を含める。

- 変更の要約
- 背景または目的
- 主な実装内容
- 必要に応じた設計判断・参照情報

ユーザー指定のメッセージがある場合は、内容・構成を勝手に変更しない。`--no-verify`、`--no-gpg-sign`、`--amend` は使わない。

```bash
git commit -m "<title>" -m "<body>"
```

コミット後に次を確認する。

```bash
git status --short --branch
git log -1 --oneline
```

コミットフックがファイルを変更した場合は、その変更を自動的にamendせず、状態を報告して停止する。コミットが成功した後にプッシュが失敗しても、`reset` や自動修正を行わず、コミットハッシュを報告する。

### 5. プッシュ先とリモート状態を確認する

アップストリームとリモートの先行状態を確認する。

```bash
git branch -vv
git rev-parse --abbrev-ref --symbolic-full-name '@{u}'
git log '@{u}..HEAD' --oneline
git log 'HEAD..@{u}' --oneline
```

- アップストリームが設定済みなら、そのブランチへ `git push` する
- アップストリームがなく、`origin` が1つだけ存在するなら、現在のブランチ名を確認して `git push -u origin <branch>` を使う
- `origin` がない、または複数の候補から選ぶ必要がある場合は停止して確認を求める
- リモートが先行またはローカルと分岐している場合は停止し、pull/rebaseなどの判断をユーザーに委ねる。自動でpull、rebase、mergeを行わない
- Force push が必要な場合は、このスキルでは実行しない。特に `main`、`master`、`develop` へのforce pushは禁止する

### 6. プッシュして結果を検証する

通常のfast-forwardプッシュだけを実行する。

```bash
git push
```

アップストリーム未設定時だけ、確認済みのリモートとブランチに対して次を使う。

```bash
git push -u origin <branch>
```

成功後に次を確認し、ローカルの未コミット変更と未プッシュコミットを報告する。

```bash
git status --short --branch
git log '@{u}..HEAD' --oneline
```

## GitHub CLIを使う場合

このスキルの通常処理は `git` だけで完結させる。認証、リモート情報、チェック結果などのために `gh` を使う必要が生じた場合は、sandbox・restricted execution内で実行しない。通常のmacOSユーザーコンテキストで実行し、キーチェーンを含む実際の認証状態を確認する。

```bash
gh auth status -h github.com
```

Restricted executionで `The token in default is invalid` などと表示されても、それだけでトークン期限切れや再認証必要とは判断しない。先に通常コンテキストで `gh auth status -h github.com` を確認し、認証と必要スコープが有効なら再認証せずに処理を続ける。最終的なリモートプッシュも、必要に応じて同じ通常コンテキストで検証する。

## 禁止事項

- `git -C`、`git reset --hard`、`git clean`、無確認のcheckoutによる変更破棄を行わない
- `git config` を変更しない
- Hookをスキップしない
- Force pushを行わない
- 対象外のユーザー変更をステージ、コミット、破棄しない
- Push失敗時に自動で履歴を書き換えない

## 完了報告

成功時は次を簡潔に報告する。

- ステージしたファイル
- コミットハッシュとメッセージ
- プッシュ先のリモート・ブランチ
- 検証した状態
- 残った未コミット変更または未確認事項

途中停止時は、実行済みの段階、停止理由、コミット済みかどうか、ユーザー変更を保持したかを明示する。

## 使用例

```text
Use $git-add-commit-push. src/app.ts と tests/app.test.ts をコミットしてpushし、メッセージは「ログイン処理を更新」にしてください。
```

```text
Use $git-add-commit-push. 今回の変更をコミットしてpushしてください。
```

```text
Use $git-add-commit-push. 全変更を確認してコミットし、現在のブランチへpushしてください。
```

参考実装： https://github.com/biwakonbu/cc-plugins/tree/main/plugins/git-actions
