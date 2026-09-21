# Remote Git backend

Local worktreeを利用できずGitHub read/writeが利用可能な `remote-only` 実行で、Test Implementation / Implementationのcandidate checkpointに使用します。CloseはローカルGit専用とし、このbackendから既定ブランチへ公開しません。

## Candidate checkpoint

1. Issueのcandidate refを一意に決める
2. 書込み直前に対象ref、candidate ref、基準SHA、承認済みテストmanifestをreadbackする
3. 許可範囲だけをblob → tree → commitで候補へ固定する
4. 候補のcandidate ref更新はnon-forceのfast-forwardだけを使う
5. 書込み後にcandidate ref、candidate SHA、親、変更パス、許可済みcommit列をreadbackする
6. 候補のcandidate SHA／baseline SHA／candidate ref／検証結果をdeliveryへ保存しreadbackする

Human Acceptance前にdefault branchを更新しません。Force、履歴書換え、squash、rebase、PR mergeで別SHAを生成して迂回しません。候補SHAは公開完了まで変換せず、そのまま保持します。

## Safety contract

このブロックがremote Git backendの単一の規範的な安全条件です。値は `workflow.toml[git_backends.remote.safety]` と一致させ、別の値を本文へ定義しません。

```toml
[git_backends.remote.safety]
candidate_ref_required = true
force_update_allowed = false
pre_write_readback_required = true
post_write_readback_required = true
default_branch_update_before_acceptance = false
on_diverged = "BLOCKED"
```

Closeの公開・CI・再開条件は [close.md](close.md) に従い、ローカルGitで実行します。リモートの候補作成で得たcandidate SHA/refと証跡はそのまま引き継ぎます。
