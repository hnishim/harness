# Remote Git backend

Local worktreeを利用できずGitHub read/writeが利用可能な `remote-only` 実行では、Issue専用のGitHub作業ブランチを使います。ローカルと同じcandidate ref／コミット履歴を継続し、default branchを未受入の作業候補にしません。Closeは [close.md](close.md) の共通手順に従います。

## 候補コミットの保存

1. 対象リポジトリ・公開先・Issueのcandidate refと基準SHAを一意に特定し、既存の作業と承認済みテストを確認する
2. 書込み直前に公開先のref、候補ブランチのref、比較元のコミットSHA、承認済みテストのmanifestを再取得して確認する
3. 許可された変更だけをblob → tree → commitの順に作成し、候補コミットとして保存する
4. 候補ブランチのrefは強制更新せず、fast-forwardできる場合だけ更新する。並行した更新、候補の作成元・変更履歴が不明な場合、許可外の変更がある場合はBLOCKEDとして停止する
5. 書込み後に候補ブランチのref、候補コミットのSHAと親コミット、変更したパス、許可済みコミットの履歴を再取得して確認する
6. 候補コミットのSHA／比較元のコミットSHA／候補ブランチのref／検証結果をdeliveryへ保存し、再取得して確認する

Human Acceptanceと明示Close指示前にdefault branchを更新しません。Force、無断reset／stash、履歴書換えで他の作業を消しません。通常のPull Request統合で公開SHAが変わることは、候補内容の変更とは区別します。

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
