# リモートGit実行担当

このreferenceは `remote-implementation-loop` のGitHub API / connector transportだけを所有します。workflow semanticsは `../../implementation-loop/` がSource of Truthです。

## checkpoint

1. Issueの候補 branchを一意に決める
2. write直前にtarget/default branch、候補 branch（存在する場合）、base commitを再取得確認し、Planで承認されたbaselineからstaleになっていないことを確認する
3. Plan 範囲の変更だけをGitHubの `blob` → `tree` → `commit` で1 候補 commitへ固定する。approved-testsはTest Reviewで固定した内容とhashを維持する
4. 候補 branchがなければ確認済みbaseから作成し、更新は **non-force** fast-forwardのref updateだけを使う
5. mutation後にbranch `ref`、候補 SHA、parent/base、変更path、範囲/provenanceを再取得確認する
6. 候補 SHA / base SHA / remote/ref / 検証結果をLinearへ保存して再取得確認する

Human Acceptance前に`main`/default branchを更新しません。force update、history rewrite、PR merge、squash、rebaseで別SHAを作るfallbackは禁止です。

## publish checkpoint

Accepted **候補 SHA** を新しいcommitへ変換せず、Close先target refへnon-force fast-forwardします。

1. publish直前にtarget ref、候補 ref、候補 ancestry、Linearに記録された候補/outgoing provenanceを再取得確認する
2. targetが候補のancestorで、outgoing chainが許可checkpoint列と一致する場合だけ同じ候補 SHAへのnon-force ref updateを行う
3. 初回publishが拒否・失敗・結果不明でも、無条件retryせずtarget refを再取得確認する
4. 再取得確認でtargetが既に候補なら成功として扱い、retryしない
5. targetが未変更で候補/outgoing provenanceも不変、remote先行/分岐なしと再確認できた場合だけ、**同一non-force操作を1回だけretry**する
6. targetが進んだ、diverged、provenance不一致、再取得確認不能ならretryせずBLOCKED
7. 1回だけretryしても失敗した場合はGit publication execution 境界としてlocal executorへ引き継ぎし、候補 SHA、target ref、outgoing chain、publish operation、expected result、未完了理由をLinearへ残す

PR merge / squash / rebase等でAccepted 候補とは別SHAを生成して迂回しません。
