# Remote Git backend

Local worktreeを利用できずGitHub read/writeが利用可能な `remote-only` 実行では、Issue専用のGitHub作業ブランチを使います。ローカルと同じcandidate ref／コミット履歴を継続し、default branchを未受入の作業候補にしません。Closeは [close.md](close.md) の共通手順に従います。

## Candidate checkpoint

1. 対象リポジトリ・公開先・Issueのcandidate refと基準SHAを一意に特定し、既存の作業と承認済みテストを確認する
2. 書込み直前に対象ref、candidate ref、基準SHA、承認済みテストmanifestをreadbackする
3. 許可範囲だけをblob → tree → commitで候補へ固定する
4. 候補ref更新はnon-forceのfast-forwardだけを使う。並行更新・由来不明・許可外変更ではBLOCKEDとして停止する
5. 書込み後にcandidate ref、candidate SHA、親、変更パス、許可済みcommit列をreadbackする
6. 候補SHA／baseline SHA／candidate ref／検証結果をdeliveryへ保存しreadbackする

Human Acceptanceと明示Close指示前にdefault branchを更新しません。Force、無断reset／stash、履歴書換えで他の作業を消しません。通常のPull Request統合で公開SHAが変わることは、候補内容の変更とは区別します。

## Safety contract

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

Closeの公開・CI・再開・ローカル反映は [close.md](close.md) を参照します。GitHubの現在状態から公開済みかを確認し、候補SHAと公開SHAの同一性を一律条件にしません。
