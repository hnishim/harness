# Remote Git backend

Local worktreeを利用できずGitHub read/writeが利用可能な `remote-only` 実行で使います。通常のworkflow意味論、Status、Review、Acceptance、Closeのentry gateはlocal実行と共通です。`local-origin` のCloseは、deliveryへ記録した起点と別の明示的な切替許可がある場合だけremoteへ続行できます。

## Candidate checkpoint

1. Issueのcandidate refを一意に決める
2. 書込み直前に対象ref、candidate ref、基準SHA、承認済みテストmanifestをreadbackする
3. 許可範囲だけをblob → tree → commitで候補へ固定する
4. 候補のcandidate ref更新はnon-forceのfast-forwardだけを使う
5. 書込み後にcandidate ref、candidate SHA、親、変更パス、許可済みcommit列をreadbackする
6. 候補のcandidate SHA／baseline SHA／candidate ref／検証結果をdeliveryへ保存しreadbackする

Human Acceptance前にdefault branchを更新しません。Force、履歴書換え、squash、rebase、PR mergeで別SHAを生成して迂回しません。候補SHAは公開完了まで変換せず、そのまま保持します。

## Publish checkpoint

受理済みcandidate SHAを変換せず、対象refへnon-force fast-forwardで公開します。

1. 公開直前に対象ref、candidate ref、候補の祖先関係、allowed commit sequenceをreadbackする
2. 対象がcandidateの祖先で、送信コミット列がallowed commit sequenceと完全一致する場合だけ同じcandidate SHAへ更新する
3. 失敗・結果不明なら対象ref、candidate ref、由来、SHAをreadbackする
4. すでにcandidateなら成功として記録する
5. 対象未変更、由来不変、分岐なしを確認できた場合だけ同一non-force操作を1回だけretryする
6. 対象進行、diverged、由来不一致、readback不能ではBLOCKEDとする
7. Retry後も失敗なら停止し、remote操作を成功へ変換しない

## Safety contract

このブロックがremote Git backendの単一の規範的な安全条件です。値は `workflow.toml[git_backends.remote.safety]` と一致させ、別の値を本文へ定義しません。

```toml
[git_backends.remote.safety]
candidate_ref_required = true
force_update_allowed = false
pre_write_readback_required = true
post_write_readback_required = true
default_branch_update_before_acceptance = false
publish_preserves_candidate_sha = true
publish_requires_target_ancestor = true
publish_requires_allowed_commit_sequence = true
publish_readback_before_retry = true
publish_retry_limit = 1
on_diverged = "BLOCKED"
```

Closeの必要CI、current-evidence、明示Close指示、公開先readback、候補祖先条件、途中停止からの再開、旧指示の再利用禁止は、同じClose共通条件として `workflow.toml` と [close.md](close.md) に従います。`remote-only` はlocal同期を要求しません。`local-origin` から明示切替したCloseは `local_origin_close_sync` に未同期を記録し、同期確認前にDoneへ進めません。
