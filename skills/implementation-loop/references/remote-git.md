# Remote Git backend

local worktreeを利用できずGitHub read/writeが利用可能な場合だけ使います。ワークフロー意味論は `../workflow.toml` と `../SKILL.md` が所有します。

## checkpoint

1. Issueのcandidate refを一意に決める
2. 書込み直前に既定ref、candidate ref、基準SHAをreadbackする
3. 許可範囲だけをblob → tree → commitで候補へ固定する
4. ref更新はnon-forceのfast-forwardだけを使う
5. 書込み後にcandidate ref、candidate SHA、親、変更パスをreadbackする
6. candidate SHA／baseline SHA／candidate ref／検証結果をdeliveryへ保存しreadbackする

Human Acceptance前に既定ブランチを更新しません。force、履歴書換え、squash、rebase、PR mergeで別SHAを生成して迂回しません。

## publish checkpoint

受理済みcandidate SHAを変換せず、対象refへnon-force fast-forwardで公開します。

1. 公開直前に対象ref、candidate ref、祖先関係、allowed checkpoint列をreadbackする
2. 対象がcandidateの祖先で、送信コミット列がallowed checkpoint列と完全一致する場合だけ同じcandidate SHAへ更新する
3. 失敗・結果不明なら対象refを再取得する
4. 既にcandidateなら成功
5. 対象未変更、由来不変、分岐なしを確認できた場合だけ同一non-force操作を1回だけ再試行する
6. 対象進行、diverged、由来不一致、readback不能ではBLOCKED
7. 1回再試行後も失敗ならlocal Git executorへhandoffする

`workflow.toml[git_backends.remote.safety]` が上記の機械的安全条件の正規定義です。この文書は操作意味と証拠を説明し、別の値を持ちません。
