# リモートGit実行担当

このreferenceは `remote-implementation-loop` のGitHub API / connector通信だけを所有します。ワークフローの意味づけは `../../implementation-loop/` を正本とします。

## checkpoint

1. Issueの候補branchを一意に決める
2. 書き込み直前にtarget/default branch、候補branch（存在する場合）、base commitを再取得確認し、Planで承認されたbaselineからstaleになっていないことを確認する
3. Planの範囲の変更だけをGitHubの `blob` → `tree` → `commit` で1つの候補commitへ固定する。approved-testsはTest Reviewで固定した内容とhashを維持する
4. 候補branchがなければ確認済みbaseから作成し、更新は **non-force** fast-forwardのref更新だけを使う
5. 変更後にbranch `ref`、候補SHA、parent/base、変更path、範囲/provenanceを再取得確認する
6. 候補 SHA / base SHA / remote/ref / 検証結果をLinearへ保存して再取得確認する

Human Acceptance前に`main`/default branchを更新しません。force update、history rewrite、PR merge、squash、rebaseで別SHAを作る迂回は禁止です。

## publish checkpoint

受理済みの**候補SHA**を新しいcommitへ変換せず、Close先target refへnon-force fast-forwardします。

1. publish直前にtarget ref、候補ref、候補ancestry、Linearに記録された候補/outgoing provenanceを再取得確認する
2. targetが候補のancestorで、outgoing chainが許可checkpoint列と一致する場合だけ同じ候補SHAへのnon-force ref更新を行う
3. 初回publishが拒否・失敗・結果不明でも、無条件retryせずtarget refを再取得確認する
4. 再取得確認でtargetが既に候補なら成功として扱い、retryしない
5. targetが未変更で候補/outgoing provenanceも不変、remote先行/分岐なしと再確認できた場合だけ、**同一non-force操作を1回だけretry**する
6. targetが進んだ、diverged、provenance不一致、再取得確認不能ならretryせずBLOCKED
7. 1回だけretryしても失敗した場合はGit公開処理の実行境界としてlocal executorへ引き継ぎ、候補SHA、target ref、outgoing chain、publish operation、expected result、未完了理由をLinearへ残す

PR merge / squash / rebase等で受理済み候補とは別SHAを生成して迂回しません。
