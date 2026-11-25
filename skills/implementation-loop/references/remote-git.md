# Remote Git backend

Local worktreeを利用できずGitHub read/writeが利用可能な `remote-only` 実行では、Issue専用のGitHub作業ブランチを使います。ローカルと同じcandidate ref／コミット履歴を継続し、default branchを未受入の作業候補にしません。Closeは [close.md](close.md) の共通手順に従います。

## 候補コミットの保存（Candidate checkpoint）

1. baselineを確定してから、Issue専用candidate refを決める。記録済みbaselineがある場合は、そのSHAとcandidate ref／候補履歴の対応を検証し、記録済みSHAをそのまま再利用する
2. 書込み直前に公開先のref、候補ブランチのref、比較元のコミットSHA、承認済みテストのmanifestを再取得して確認する
3. 許可された変更だけをblob → tree → commitの順に作成し、候補コミットとして保存する
4. 候補ブランチのrefはnon-force（強制更新なし）とし、fast-forwardできる場合だけ更新する。並行した更新、候補の作成元・変更履歴が不明な場合、許可外の変更がある場合はBLOCKEDとして停止する
5. 書込み後に候補ブランチのref、候補コミットのSHAと親コミット、変更したパス、許可済みコミットの履歴を再取得して確認する
6. 候補SHA／基準SHA／候補ref／検証結果をdeliveryへ保存し、再取得して確認する

## Baselineの選択と再開

初回の承認済み書込時に既定refの履歴を確認し、そのコミットSHAをbaselineとして記録します。基準コミットがない新規リポジトリでは、次節の初期化を行います。取得失敗を未初期化とみなさず、対象や既存履歴が不明な場合は読み取りで確認します。

再開時は、deliveryに記録されたbaseline SHAの有無を確認します。記録があればLinearの内容、既定ブランチ名、Issue candidate ref、candidate SHAと親履歴を再取得して照合します。Baseline SHAが記録済みで、candidate SHAとcandidate refがどちらも未記録かつIssue refが存在しない場合は、baselineが既定ブランチから取得したSHAと一致し、記録に矛盾がなければ同じbaselineを使ってcandidate作成を続けます。これはbaseline作成後、candidate ref作成前に中断した場合の再開経路です。記録済みcandidateがある場合にbaselineを再利用できるのは、candidateの祖先にbaselineがあり、candidate refとSHAがdeliveryと一致し、既存変更の由来も確認できる場合だけです。現在の既定ブランチが進んでいてもbaselineを自動更新しません。Candidate refが未記録なのに存在する場合、baseline SHAがない状態で当該Issueの過去のcandidateやGit書込を示す記録・refがある場合、候補や履歴が記録と異なる場合、または由来を確認できない場合は停止します。当該IssueのcandidateやGit書込履歴がなく、未記録の作業がないと確認できる新規開始時は、既定refの現在SHAをbaselineとして記録します。

## 新規リポジトリの初期化

読取り専用フェーズでは書き込まず、最初の承認済み書込時に、基準コミットのない新規リポジトリを成果物なしで初期化できます。既存ref・index・作業ファイルを変更せず、書込先の既定refと既存履歴を確認します。無関係な内部refや複数の書込権限の存在だけでは停止しません。

Local Gitでは、空treeから親なしコミットを作成し、既定refへ強制更新なしでpushします。ローカルのみが公開先の場合は、既定refが存在しないことを条件とする `git update-ref refs/heads/<default-branch> <baseline-sha> ""` を使えます。作業領域やindexを初期化に流用しません。

GitHub APIのみの場合は、新規リポジトリの既定ブランチに最小READMEを新規作成できます。Contents APIで既存ファイルの更新用SHAを指定せず、既存内容を置換しません。このAPIはブランチ未作成を原子的に保証しないため、可能ならLocal Gitを優先します。並行初期化や応答不明時は再取得し、既存履歴を上書きせず、現在の状態に応じた通常のbaseline選択または再開手順へ戻ります。

初期化後は既定refとそのSHAを再取得してbaselineを記録し、そのSHAからIssue専用candidate ref／worktreeを作成します。初期化コミットに実装・テスト成果物を含めません。既存作業や候補との対応が不明なら通常の安全条件に従います。

成果物を含まない新規リポジトリの初期化を除き、Human Acceptanceと明示Close指示前にdefault branchを更新しません。Force、無断reset／stash、履歴書換えで他の作業を消しません。通常のPull Request統合で公開SHAが変わることは、候補内容の変更とは区別します。

## 候補コミットを保存する際の安全条件

候補作成の安全条件は `workflow.toml[git_backends.remote.safety]` と一致させます。

```toml
[git_backends.remote.safety]
candidate_ref_required = true
force_update_allowed = false
pre_write_readback_required = true
post_write_readback_required = true
default_branch_update_before_acceptance = false
on_diverged = "BLOCKED"
```

Closeでの公開・CI確認・再開・ローカル環境への反映は [close.md](close.md) を参照します。GitHubの現在状態から公開済みかを確認し、候補SHAと公開SHAの同一性を一律条件にしません。
