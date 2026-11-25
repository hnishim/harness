# Remote Git backend

Local worktreeを利用できずGitHub read/writeが利用可能な `remote-only` 実行では、Issue専用のGitHub作業ブランチを使います。ローカルと同じcandidate ref／コミット履歴を継続し、default branchを未受入の作業候補にしません。Closeは [close.md](close.md) の共通手順に従います。

## 候補コミットの保存（Candidate checkpoint）

1. `workflow.toml[git_initialization]` に従ってbaselineを確定してから、Issue専用candidate refを決める。記録済みbaselineがある場合は、そのSHAとcandidate ref／候補履歴の対応を検証し、記録済みSHAをそのまま再利用する
2. 書込み直前に公開先のref、候補ブランチのref、比較元のコミットSHA、承認済みテストのmanifestを再取得して確認する
3. 許可された変更だけをblob → tree → commitの順に作成し、候補コミットとして保存する
4. 候補ブランチのrefはnon-force（強制更新なし）とし、fast-forwardできる場合だけ更新する。並行した更新、候補の作成元・変更履歴が不明な場合、許可外の変更がある場合はBLOCKEDとして停止する
5. 書込み後に候補ブランチのref、候補コミットのSHAと親コミット、変更したパス、許可済みコミットの履歴を再取得して確認する
6. 候補SHA／基準SHA／候補ref／検証結果をdeliveryへ保存し、再取得して確認する

## Baselineの選択と再開

Baselineの作成と再利用は `workflow.toml[git_initialization]` で制御します。既存リポジトリで履歴がある場合、初回の書込前に確認した既定ブランチのコミットSHAをbaselineとし、その履歴上にIssue専用candidate refを作成します。空リポジトリ初期化の条件は適用しません。

再開時は、deliveryに記録されたbaseline SHAの有無を確認します。記録があればLinearの内容、既定ブランチ名、Issue candidate ref、candidate SHAと親履歴を再取得して照合します。Baseline SHAが記録済みで、candidate SHAとcandidate refがどちらも未記録かつIssue refが存在しない場合は、baselineが既定ブランチから取得したSHAと一致し、記録に矛盾がなければ同じbaselineを使ってcandidate作成を続けます。これはbaseline作成後、candidate ref作成前に中断した場合の再開経路です。記録済みcandidateがある場合にbaselineを再利用できるのは、candidateの祖先にbaselineがあり、candidate refとSHAがdeliveryと一致し、既存変更の由来も確認できる場合だけです。現在の既定ブランチが進んでいてもbaselineを自動更新しません。Candidate refが未記録なのに存在する場合、候補や履歴が記録と異なる場合、または由来を確認できない場合は停止します。

GitHub APIで初期化書込の応答が途切れた場合、まず読み取り専用でリポジトリ情報、既定ブランチ名、ref、コミット、ツリーとREADME内容を再取得します。既定ブランチ名が書込前と同じで、既定refが今回の応答またはdeliveryで確認済みのSHAを指し、そのSHAに親がなく、treeがREADMEだけを含み、READMEのバイト列も要求値と一致する場合に限り、そのSHAをbaselineとして記録し通常のcandidate手順へ進みます。既知のSHAと一致しない状態、以前の書込を示す記録、または予想外のref・内容が見つかった場合は読み取り専用のまま停止します。Local Gitのpush応答が途切れた場合も、既知のbaseline SHAと提供元の既定refを読み取り専用で照合します。既定refがそのSHAを指す場合だけ続行し、refがない／空の状態へ変わった場合や別のSHAを指す場合は、進行中のpushがないことを確認できるまで再試行せず停止します。

## 空のリポジトリの初期化

空の新規リポジトリは基準SHAがない正常な状態です。Planningなどの読取り専用フェーズでは初期化しません。最初の承認済み書込の直前に限り、次の全条件を確認できた場合にAgentが実装成果物を含まない最小READMEを作成し、基準コミットとして初期化できます。HIR専用の新規リポジトリとして書込担当を単独に割り当てた状態は排他条件を満たせるため、人間による事前初期化は不要です。

1. Issue、対象リポジトリ、owner/repository、認証済みGitHub APIの書込先が一致することを確認する
2. リポジトリ情報から既定ブランチ名を取得する。値が空、取得不能、または候補が複数なら停止する
3. `GET /repos/{owner}/{repo}/branches` が空配列を返すことを確認する。`GET /repos/{owner}/{repo}/git/matching-refs/` と `/commits` は、この実行で確認したGitHub APIではともにHTTP `409` と本文 `Git Repository is empty.` を返した。応答本文まで照合し、ブランチ一覧とも一致する場合だけ空状態と判断する。HTTP `409` だけでは空と判定しない。権限・通信・対象不存在のエラーや応答の不一致があれば停止する
4. 初期化確認から初回書込・readbackまで、他のAgentや利用者が同リポジトリへ書き込まない排他条件を確保する。排他条件がなく、または書込前に状態が変わった場合は停止する
5. 既定ブランチを明示せず `PUT /repos/{owner}/{repo}/contents/README.md` を呼び、`sha` も指定しない。READMEにはリポジトリ名の見出しだけを記載し、コード、テスト、成果物を含めない。この初回作成だけを空リポジトリ初期化として許可する。同じパスの既存ファイルを更新するには `sha` が必要となるため、この要求は初回作成だけに使える。失敗時に別パスへの切替や再試行をせず、読み取り専用で照合する
6. 応答が失敗または不明な場合は、前節「Baselineの選択と再開」の読取り専用照合を適用する
7. 成功後にリポジトリ情報を再取得し、既定ブランチ名が書込前と同じことを確認する。そのブランチref、コミットSHA、親コミットがないこと、ツリーにREADMEだけがあることも再取得して確認する。確認済みSHAを指定してREADME内容も再取得し、作成した見出しのバイト列と一致することを確認する。条件と異なる場合は追加・修復書込をせず停止する
8. 確認したコミットSHAをbaselineとして記録し、以降は通常手順のIssue専用candidate refを使う。README初期化コミットは実装候補、テスト候補、受入対象に含めない

このGitHub Contents APIには期待する未初期化refを条件にする機能がないため、排他条件は必須です。既定ブランチにrefがある、READMEがすでにある、履歴・ツリーが空でない、API応答が曖昧、権限不足、同時更新、またはreadback不一致の場合は初期化を試みず／再試行せず停止します。初期化以外の既存リポジトリではこの例外を使わず、既存履歴を保護します。

Local Git backendでは、IssueでGitHub remoteが対象に指定されている場合、まず `git remote get-url origin` が成功することを確認します。Remoteが存在しない、取得に失敗した、または認証情報を確認できない場合は停止し、空状態とは扱いません。`git ls-remote --refs origin` を成功させて全refを確認し、続けて `git fetch origin` を正常完了させます。リポジトリ情報から既定ブランチ名を取得し、そのrefを照合します。既定refに履歴がある場合はそのSHAをbaselineとして使い、初期化せず、そのSHAからIssue専用candidate worktreeを作ります。他refが存在するのに既定refを確認できない場合は停止します。全refが空ならローカルの `git for-each-ref --format='%(refname)'` も空であること、独立した作業領域が空でHEADにコミットがなく、stage済み・未追跡のファイルもないことを確認し、空リポジトリ初期化の条件を続けて適用します。Gitの空treeから親なしコミットを作り、既定refへ通常の強制更新なしpushを行って、結果を提供元から読み直します。既定refの作成に成功してもcandidate refがまだない場合はdeliveryのbaselineとref状態を読み直し、candidate refを確認済みbaseline SHAから作ります。`git commit --allow-empty` はindexの内容を含めるため使わず、コミットのtreeが空であることをpush前に確認します。以下はコミット作成と強制更新なしpushの例です。

```sh
empty_tree=$(git mktree </dev/null)
baseline=$(printf '%s\n' 'Initialize repository baseline' | git commit-tree "$empty_tree")
git push origin "$baseline:refs/heads/<default-branch>"
```

IssueでGitHub remoteが対象に指定されているのにremote未設定、取得失敗、またはrefが空でない場合は停止します。Remoteなしのリポジトリも、Issueが当該ローカルリポジトリの既定refを公開先と指定し、close.mdのローカル統合条件を満たすなら対象にできます。この場合は既定refの作成時に空の旧値を期待値として指定し、refがまだ存在しない場合だけ更新する `git update-ref refs/heads/<default-branch> <baseline-sha> ""` を使います。通常更新や強制更新で既存refを置換しません。既定ブランチ名、全refの不存在、空の作業領域、HEADの不存在、排他条件のいずれかを確認できない場合、pushまたはref作成が競合／不明な結果になった場合、readbackが期待と異なる場合は停止し、既存コミットを変更しません。Baseline確認後、ローカルのcandidate worktreeは確認済みSHAから `git worktree add -b <issue-branch> <worktree-path> <baseline-sha>` で作ります。Candidate refを別のHEADや未確認の既定ブランチ先端から作りません。

初期化の適格条件を満たすbaseline作成を除き、Human Acceptanceと明示Close指示前にdefault branchを更新しません。Force、無断reset／stash、履歴書換えで他の作業を消しません。通常のPull Request統合で公開SHAが変わることは、候補内容の変更とは区別します。

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
